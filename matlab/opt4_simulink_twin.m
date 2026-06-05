function R = opt4_simulink_twin(D, smart_profile, R3, outdir)
% OPT4_SIMULINK_TWIN  Build a Simulink digital twin of the charging hub and
%   validate it against the Option-3 MATLAB energy-management model.
%   The twin: From Workspace (PV, load) -> MATLAB Function EMS controller
%   (battery state-of-charge) -> To Workspace (grid, SoC). It is constructed
%   programmatically (no manual clicking) and run headlessly via sim().

mdl = 'chargingHubTwin';

% ---- inputs (identical to Option 3 so the twin must reproduce it) -----------
pv_kwp = R3.pv_kwp; batt_kwh = R3.batt_kwh;
d0 = (183-1)*24 + 1;
pv_day = D.pv_per_kwp(d0:d0+23) * pv_kwp;
load   = smart_profile(:);
t = (0:23)';
assignin('base', 'pv_ts',   timeseries(pv_day, t));
assignin('base', 'load_ts', timeseries(load,   t));

usable = batt_kwh * D.dod; eta = sqrt(D.eta_rt); pmax = batt_kwh * 0.5;

% ---- (re)build the model ----------------------------------------------------
if bdIsLoaded(mdl); close_system(mdl, 0); end
new_system(mdl);

add_block('simulink/Sources/From Workspace',      [mdl '/PV']);
set_param([mdl '/PV'],   'VariableName','pv_ts',   'Interpolate','off', 'OutputAfterFinalValue','Holding final value');
add_block('simulink/Sources/From Workspace',      [mdl '/Load']);
set_param([mdl '/Load'], 'VariableName','load_ts', 'Interpolate','off', 'OutputAfterFinalValue','Holding final value');
set_param([mdl '/PV'],   'Position',[40 40 120 80]);
set_param([mdl '/Load'], 'Position',[40 140 120 180]);

add_block('simulink/User-Defined Functions/MATLAB Function', [mdl '/EMS']);
set_param([mdl '/EMS'], 'Position',[220 60 360 170]);

add_block('simulink/Sinks/To Workspace', [mdl '/gridOut']);
set_param([mdl '/gridOut'], 'VariableName','grid_out', 'SaveFormat','Array', 'Position',[460 60 560 90]);
add_block('simulink/Sinks/To Workspace', [mdl '/socOut']);
set_param([mdl '/socOut'], 'VariableName','soc_out',  'SaveFormat','Array', 'Position',[460 140 560 170]);

% EMS controller code (battery dispatch with persistent SoC state)
code = sprintf([ ...
 'function [grid, soc_out] = EMS(pv, load)\n' ...
 'persistent soc\n' ...
 'usable = %.6f; eta = %.6f; pmax = %.6f;\n' ...
 'if isempty(soc); soc = usable*0.5; end\n' ...
 'a = min(pv, load); res = load - a; sur = pv - a;\n' ...
 'if sur > 0\n' ...
 '    room = (usable - soc)/eta; c = min([sur, pmax, room]); if c<0; c=0; end\n' ...
 '    soc = soc + c*eta; sur = sur - c;\n' ...
 'end\n' ...
 'g = 0;\n' ...
 'if res > 0\n' ...
 '    if soc > 0\n' ...
 '        dis = min([res, pmax, soc*eta]); soc = soc - dis/eta; res = res - dis;\n' ...
 '    end\n' ...
 '    g = res;\n' ...
 'end\n' ...
 'grid = g; soc_out = soc;\n'], usable, eta, pmax);
sf = sfroot;
chart = sf.find('-isa','Stateflow.EMChart','-and','Path',[mdl '/EMS']);
chart.Script = code;

% ---- wire it up -------------------------------------------------------------
add_line(mdl, 'PV/1',   'EMS/1', 'autorouting','on');
add_line(mdl, 'Load/1', 'EMS/2', 'autorouting','on');
add_line(mdl, 'EMS/1',  'gridOut/1', 'autorouting','on');
add_line(mdl, 'EMS/2',  'socOut/1',  'autorouting','on');

% ---- discrete solver, 24 hourly steps --------------------------------------
set_param(mdl, 'Solver','FixedStepDiscrete', 'FixedStep','1', ...
    'StartTime','0', 'StopTime','23', 'SaveOutput','off');
save_system(mdl, fullfile(outdir, [mdl '.slx']));

simOut = sim(mdl);
grid_tw = simOut.get('grid_out'); grid_tw = grid_tw(:);
soc_tw  = simOut.get('soc_out');  soc_tw  = soc_tw(:);
% align lengths to 24 hourly samples
n = min([24, numel(soc_tw), numel(grid_tw)]);
soc_tw = soc_tw(1:n); grid_tw = grid_tw(1:n);

% ---- validate against Option 3 MATLAB EMS -----------------------------------
soc_ml = R3.soc(:); soc_ml = soc_ml(1:n);
soc_err = abs(soc_tw - soc_ml);
R.max_soc_err_kwh = max(soc_err);
R.max_soc_err_pct = 100 * max(soc_err) / max(usable, eps);
gi_tw = sum(grid_tw); gi_ml = sum(R3.gridv);
R.grid_err_pct = 100 * abs(gi_tw - gi_ml) / max(gi_ml, eps);

% ---- plot overlay -----------------------------------------------------------
tt = t(1:n);
f = figure('Visible','off','Position',[100 100 900 420]); hold on; grid on;
plot(tt, 100*soc_ml/usable, '-o', 'LineWidth',2, 'Color',[0.10 0.10 0.23], ...
    'DisplayName','MATLAB EMS (Option 3)', 'MarkerSize',4);
plot(tt, 100*soc_tw/usable, '--s', 'LineWidth',1.8, 'Color',[0.18 0.49 0.20], ...
    'DisplayName','Simulink digital twin', 'MarkerSize',4);
xlabel('Hour of day'); ylabel('Battery SoC (%)');
title(sprintf('Option 4 — Simulink digital twin validates EMS (max error %.2f%%)', R.max_soc_err_pct));
legend('Location','best'); xlim([0 23]);
exportgraphics(f, fullfile(outdir, 'matlab_opt4_digital_twin.png'), 'Resolution', 150);
close(f);

if bdIsLoaded(mdl); close_system(mdl, 0); end
fprintf('\n[Option 4] Simulink digital twin built + simulated:\n');
fprintf('   SoC match vs MATLAB EMS: max error %.3f kWh (%.2f%%) | grid error %.2f%%\n', ...
    R.max_soc_err_kwh, R.max_soc_err_pct, R.grid_err_pct);
end
