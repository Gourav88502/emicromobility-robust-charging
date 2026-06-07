function R = opt4_simulink_twin(D, smart_profile, R3, outdir)
% OPT4_SIMULINK_TWIN  Build a Simulink digital twin of the charging hub and
%   validate it against the Option-3 MATLAB energy-management model.
%   Callable with NO arguments — upstream options run automatically.
%   If Simulink is unavailable the function falls back to a pure-MATLAB twin
%   (same EMS logic, no graphical model required).

% ---- auto-load defaults when called with no arguments -----------------------
if nargin < 1 || isempty(D)
    fprintf('[Option 4] No data struct supplied — calling load_project_data()...\n');
    D = load_project_data();
end
if nargin < 2 || isempty(smart_profile)
    fprintf('[Option 4] No smart_profile supplied — running opt2 first...\n');
    R2 = opt2_smart_charging_lp(D);
    smart_profile = R2.smart_profile;
end
if nargin < 3 || isempty(R3)
    fprintf('[Option 4] No R3 supplied — running opt3 first...\n');
    R3 = opt3_solar_battery_ems(D, smart_profile);
end
if nargin < 4 || isempty(outdir)
    here   = fileparts(mfilename('fullpath'));
    outdir = fullfile(here, '..', 'outputs', 'matlab');
    if ~exist(outdir, 'dir'); mkdir(outdir); end
end

% ---- shared parameters ------------------------------------------------------
mdl      = 'chargingHubTwin';
pv_kwp   = R3.pv_kwp;
batt_kwh = R3.batt_kwh;
d0       = (183 - 1) * 24 + 1;
d1       = d0 + 23;
if numel(D.pv_per_kwp) < d1
    idx    = mod((d0:d1) - 1, numel(D.pv_per_kwp)) + 1;
    pv_day = D.pv_per_kwp(idx) * pv_kwp;
else
    pv_day = D.pv_per_kwp(d0:d1) * pv_kwp;
end
load_h  = smart_profile(:);
t       = (0:23)';
usable  = batt_kwh * D.dod;
eta     = sqrt(D.eta_rt);
pmax    = batt_kwh * 0.5;

% ---- try Simulink first; fall back to MATLAB-only twin ----------------------
sim_ok = license('test', 'Simulink');

if sim_ok
    try
        % Export timeseries for Simulink
        assignin('base', 'pv_ts',   timeseries(pv_day, t));
        assignin('base', 'load_ts', timeseries(load_h, t));

        % (Re)build the model programmatically
        if bdIsLoaded(mdl); close_system(mdl, 0); end
        new_system(mdl);

        add_block('simulink/Sources/From Workspace', [mdl '/PV']);
        set_param([mdl '/PV'],   'VariableName', 'pv_ts',   ...
            'Interpolate', 'off', 'OutputAfterFinalValue', 'Holding final value');
        add_block('simulink/Sources/From Workspace', [mdl '/Load']);
        set_param([mdl '/Load'], 'VariableName', 'load_ts', ...
            'Interpolate', 'off', 'OutputAfterFinalValue', 'Holding final value');
        set_param([mdl '/PV'],   'Position', [40  40 120  80]);
        set_param([mdl '/Load'], 'Position', [40 140 120 180]);

        add_block('simulink/User-Defined Functions/MATLAB Function', [mdl '/EMS']);
        set_param([mdl '/EMS'], 'Position', [220 60 360 170]);

        add_block('simulink/Sinks/To Workspace', [mdl '/gridOut']);
        set_param([mdl '/gridOut'], 'VariableName', 'grid_out', ...
            'SaveFormat', 'Array', 'Position', [460  60 560  90]);
        add_block('simulink/Sinks/To Workspace', [mdl '/socOut']);
        set_param([mdl '/socOut'], 'VariableName', 'soc_out',  ...
            'SaveFormat', 'Array', 'Position', [460 140 560 170]);

        % EMS MATLAB Function code
        code = sprintf([ ...
         'function [grid, soc_out] = EMS(pv, load)\n' ...
         'persistent soc\n' ...
         'usable = %.6f; eta = %.6f; pmax = %.6f;\n' ...
         'if isempty(soc); soc = usable*0.5; end\n' ...
         'a = min(pv, load); res = load - a; sur = pv - a;\n' ...
         'if sur > 0\n' ...
         '    room = (usable - soc)/eta; c = min([sur, pmax, room]);\n' ...
         '    if c < 0; c = 0; end\n' ...
         '    soc = soc + c*eta; sur = sur - c;\n' ...
         'end\n' ...
         'g = 0;\n' ...
         'if res > 0\n' ...
         '    if soc > 0\n' ...
         '        dis = min([res, pmax, soc*eta]);\n' ...
         '        if dis < 0; dis = 0; end\n' ...
         '        soc = soc - dis/eta; res = res - dis;\n' ...
         '    end\n' ...
         '    g = max(res, 0);\n' ...
         'end\n' ...
         'grid = g; soc_out = soc;\n'], usable, eta, pmax);

        % Set the MATLAB Function block code via Stateflow API
        sf    = sfroot;
        chart = sf.find('-isa', 'Stateflow.EMChart', '-and', 'Path', [mdl '/EMS']);
        if ~isempty(chart)
            chart.Script = code;
        end

        add_line(mdl, 'PV/1',   'EMS/1', 'autorouting', 'on');
        add_line(mdl, 'Load/1', 'EMS/2', 'autorouting', 'on');
        add_line(mdl, 'EMS/1',  'gridOut/1', 'autorouting', 'on');
        add_line(mdl, 'EMS/2',  'socOut/1',  'autorouting', 'on');

        set_param(mdl, 'Solver', 'FixedStepDiscrete', 'FixedStep', '1', ...
            'StartTime', '0', 'StopTime', '23', 'SaveOutput', 'off');
        save_system(mdl, fullfile(outdir, [mdl '.slx']));

        simOut   = sim(mdl);
        grid_tw  = simOut.get('grid_out'); grid_tw = grid_tw(:);
        soc_tw   = simOut.get('soc_out');  soc_tw  = soc_tw(:);
        n        = min([24, numel(soc_tw), numel(grid_tw)]);
        soc_tw   = soc_tw(1:n);
        grid_tw  = grid_tw(1:n);

        if bdIsLoaded(mdl); close_system(mdl, 0); end
        used_simulink = true;
        fprintf('[Option 4] Simulink model built and simulated OK.\n');

    catch ME
        fprintf('[Option 4] Simulink build/sim failed (%s)\n  -> falling back to MATLAB-only twin.\n', ...
            ME.message);
        if bdIsLoaded(mdl); close_system(mdl, 0); end
        sim_ok = false;
    end
end

if ~sim_ok
    % ---- Pure-MATLAB fallback twin (same EMS logic as opt3) -----------------
    fprintf('[Option 4] Running MATLAB-only digital twin (Simulink not available).\n');
    soc      = usable * 0.5;
    soc_tw   = zeros(24, 1);
    grid_tw  = zeros(24, 1);
    for h = 1:24
        g   = pv_day(h);
        dmd = load_h(h);
        a   = min(g, dmd);
        res = dmd - a;
        sur = g - a;
        if sur > 0
            room = (usable - soc) / eta;
            c    = max(min([sur, pmax, room]), 0);
            soc  = soc + c * eta;
        end
        if res > 0 && soc > 0
            dis  = max(min([res, pmax, soc * eta]), 0);
            soc  = soc - dis / eta;
            res  = res - dis;
        end
        grid_tw(h) = max(res, 0);
        soc_tw(h)  = soc;
    end
    n = 24;
    used_simulink = false;
end

% ---- Validate twin vs Option-3 MATLAB EMS -----------------------------------
soc_ml     = R3.soc(1:n);
soc_err    = abs(soc_tw - soc_ml);
R.max_soc_err_kwh = max(soc_err);
R.max_soc_err_pct = 100 * max(soc_err) / max(usable, eps);
gi_tw      = sum(grid_tw);
gi_ml      = sum(R3.gridv);
R.grid_err_pct = 100 * abs(gi_tw - gi_ml) / max(gi_ml, eps);
R.soc_twin     = soc_tw;
R.grid_twin    = grid_tw;
R.used_simulink = used_simulink;

% ---- plot -------------------------------------------------------------------
tt = t(1:n);
f = figure('Visible', 'off', 'Position', [100 100 900 420]);
hold on; grid on;
plot(tt, 100 * soc_ml / usable, '-o', 'LineWidth', 2, ...
    'Color', [0.10 0.10 0.23], 'DisplayName', 'MATLAB EMS (Option 3)', 'MarkerSize', 4);
plot(tt, 100 * soc_tw / usable, '--s', 'LineWidth', 1.8, ...
    'Color', [0.18 0.49 0.20], 'DisplayName', ...
    sprintf('%s twin', iif(used_simulink, 'Simulink', 'MATLAB')), 'MarkerSize', 4);
xlabel('Hour of day'); ylabel('Battery SoC (%)');
title(sprintf('Option 4 — Digital twin validates EMS (max SoC error %.2f%%)', ...
    R.max_soc_err_pct));
legend('Location', 'best'); xlim([0 23]);
exportgraphics(f, fullfile(outdir, 'matlab_opt4_digital_twin.png'), 'Resolution', 150);
close(f);

fprintf('\n[Option 4] Digital twin validation (%s):\n', ...
    iif(used_simulink, 'Simulink model', 'MATLAB-only fallback'));
fprintf('   Max SoC error vs MATLAB EMS : %.3f kWh  (%.2f%%)\n', ...
    R.max_soc_err_kwh, R.max_soc_err_pct);
fprintf('   Grid energy error           : %.2f%%\n', R.grid_err_pct);
end

% ---- tiny helper so we avoid nested ifs in fprintf --------------------------
function out = iif(cond, a, b)
if cond; out = a; else; out = b; end
end
