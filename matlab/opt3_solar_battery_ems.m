function R = opt3_solar_battery_ems(D, smart_profile, outdir)
% OPT3_SOLAR_BATTERY_EMS  Solar + battery + charging-load energy management.
%   Callable with NO arguments — runs opt2 automatically if smart_profile is
%   not supplied. Also callable from run_matlab_study.

% ---- auto-load defaults when called with no arguments -----------------------
if nargin < 1 || isempty(D)
    fprintf('[Option 3] No data struct supplied — calling load_project_data()...\n');
    D = load_project_data();
end
if nargin < 2 || isempty(smart_profile)
    fprintf('[Option 3] No smart_profile supplied — running opt2 first...\n');
    R2 = opt2_smart_charging_lp(D);
    smart_profile = R2.smart_profile;   % 24x1 LP-optimal hourly schedule
end
if nargin < 3 || isempty(outdir)
    here   = fileparts(mfilename('fullpath'));
    outdir = fullfile(here, '..', 'outputs', 'matlab');
    if ~exist(outdir, 'dir'); mkdir(outdir); end
end

% ---- EMS parameters ---------------------------------------------------------
pv_kwp   = 25;
batt_kwh = 30;
eta      = sqrt(D.eta_rt);          % one-way efficiency
usable   = batt_kwh * D.dod;
pmax     = batt_kwh * 0.5;          % 0.5C power limit

% Representative sunny summer day from the real PVGIS series (day ~183)
d0     = (183 - 1) * 24 + 1;
d1     = d0 + 23;
if numel(D.pv_per_kwp) < d1
    % Short series fallback — wrap with mod
    idx = mod((d0:d1) - 1, numel(D.pv_per_kwp)) + 1;
    pv_day = D.pv_per_kwp(idx) * pv_kwp;
else
    pv_day = D.pv_per_kwp(d0:d1) * pv_kwp;     % kWh/h for the chosen day
end
load_h = smart_profile(:);          % 24x1 smart-charging target (kWh/h)

% ---- Hourly dispatch --------------------------------------------------------
soc       = usable * 0.5;
gridv     = zeros(24, 1);
pv2load   = zeros(24, 1);
bat2load  = zeros(24, 1);
pv2bat    = zeros(24, 1);
curt      = zeros(24, 1);
socv      = zeros(24, 1);

for h = 1:24
    g    = pv_day(h);
    dmd  = load_h(h);

    % 1. PV -> load
    a         = min(g, dmd);
    pv2load(h) = a;
    res       = dmd - a;
    sur       = g - a;

    % 2. Surplus PV -> battery
    if sur > 0
        room    = (usable - soc) / eta;
        c       = min([sur, pmax, room]);
        c       = max(c, 0);
        soc     = soc + c * eta;
        pv2bat(h) = c;
        sur     = sur - c;
    end
    curt(h) = max(sur, 0);

    % 3. Battery -> residual demand
    bat_d = 0;
    if res > 0 && soc > 0
        dis      = min([res, pmax, soc * eta]);
        dis      = max(dis, 0);
        soc      = soc - dis / eta;
        bat_d    = dis;
        res      = res - dis;
    end
    bat2load(h) = bat_d;
    gridv(h)    = max(res, 0);
    socv(h)     = soc;
end

served = sum(load_h);
R.solar_fraction  = (sum(pv2load) + sum(bat2load)) / max(served, 1e-9);
R.grid_import_kwh = sum(gridv);
R.pv_kwp          = pv_kwp;
R.batt_kwh        = batt_kwh;
R.soc             = socv;
R.pv2load         = pv2load;
R.bat2load        = bat2load;
R.gridv           = gridv;

% ---- plot: stacked supply + SoC ---------------------------------------------
hours = (0:23)';
f = figure('Visible', 'off', 'Position', [100 100 900 460]);
yyaxis left
ar = area(hours, [pv2load, bat2load, gridv]); grid on;
ar(1).FaceColor = [0.95 0.72 0.02];
ar(2).FaceColor = [0.18 0.49 0.20];
ar(3).FaceColor = [0.64 0.23 0.45];
ylabel('Power to load (kW)');
yyaxis right
plot(hours, 100 * socv / max(usable, eps), '--', ...
    'Color', [0.10 0.10 0.23], 'LineWidth', 2);
ylabel('Battery SoC (%)'); ylim([0 105]);
ax = gca; ax.YAxis(2).Color = [0.10 0.10 0.23];
xlabel('Hour of day');
title(sprintf('Option 3 — Solar+battery EMS: solar fraction %.0f%% (%d kWp, %d kWh)', ...
    100 * R.solar_fraction, pv_kwp, batt_kwh));
legend({'PV to load', 'Battery to load', 'Grid to load', 'Battery SoC'}, ...
    'Location', 'northwest');
xlim([0 23]);
exportgraphics(f, fullfile(outdir, 'matlab_opt3_solar_battery.png'), 'Resolution', 150);
close(f);

fprintf('\n[Option 3] Solar+battery EMS (%d kWp PV, %d kWh battery):\n', pv_kwp, batt_kwh);
fprintf('   Solar fraction  : %.0f%%\n', 100 * R.solar_fraction);
fprintf('   Grid import     : %.2f kWh/day\n', R.grid_import_kwh);
fprintf('   Battery midday  : PV charges battery, discharges into evening load\n');
end
