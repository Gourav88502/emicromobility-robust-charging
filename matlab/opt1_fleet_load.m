function R = opt1_fleet_load(D, outdir)
% OPT1_FLEET_LOAD  Charging-load simulation across fleet sizes (Option 1).
%   Callable with NO arguments — data and output directory are set automatically.
%   Also callable from run_matlab_study: R1 = opt1_fleet_load(D, outdir)

% ---- auto-load defaults when called with no arguments -----------------------
if nargin < 1 || isempty(D)
    fprintf('[Option 1] No data struct supplied — calling load_project_data()...\n');
    D = load_project_data();
end
if nargin < 2 || isempty(outdir)
    here   = fileparts(mfilename('fullpath'));
    outdir = fullfile(here, '..', 'outputs', 'matlab');
    if ~exist(outdir, 'dir'); mkdir(outdir); end
end

% ---- simulation -------------------------------------------------------------
fleets = [50 100 500];
hours  = (0:23)';

% Arrival profile: vehicles return mostly in the evening (16:00-22:00)
arr = [0.01 0.01 0.01 0.01 0.01 0.01 0.02 0.02 0.02 0.02 0.02 0.02 ...
       0.02 0.02 0.03 0.05 0.10 0.14 0.16 0.13 0.09 0.06 0.04 0.02]';
arr = arr / sum(arr);

M = 20;                       % installed charge bays
bay = D.bay_kw;               % kW per bay
depot_kw = M * bay;           % max simultaneous charging power

R.fleets    = fleets;
R.peak_kw   = zeros(1, 3);
R.energy_kwh = zeros(1, 3);
R.completion = zeros(1, 3);
profiles    = zeros(24, 3);

for i = 1:numel(fleets)
    N    = fleets(i);
    Eday = N * D.kwh_per_vehicle_day;   % total daily energy (kWh)
    % Unmanaged: charging demand follows arrivals, capped by depot power
    raw   = Eday * arr;
    served = zeros(24, 1);
    carry  = 0;
    for h = 1:24
        want      = raw(h) + carry;
        served(h) = min(want, depot_kw);
        carry     = want - served(h);
    end
    profiles(:, i)  = served;
    R.peak_kw(i)    = max(served);
    R.energy_kwh(i) = Eday;
    R.completion(i) = sum(served) / Eday;  % fraction charged within the day
end

% ---- plot -------------------------------------------------------------------
f = figure('Visible', 'off', 'Position', [100 100 900 420]);
colors = [0.26 0.53 0.67; 0.95 0.59 0.12; 0.88 0.21 0.09];
hold on; grid on;
for i = 1:3
    plot(hours, profiles(:, i), '-o', 'LineWidth', 2, 'Color', colors(i, :), ...
        'MarkerSize', 3, 'DisplayName', sprintf('%d vehicles', fleets(i)));
end
yline(depot_kw, '--k', sprintf('Depot capacity %.0f kW', depot_kw), 'LineWidth', 1.2);
xlabel('Hour of day'); ylabel('Charging load (kW)');
title('Option 1 — Unmanaged charging load by fleet size');
legend('Location', 'northwest'); xlim([0 23]);
exportgraphics(f, fullfile(outdir, 'matlab_opt1_fleet_load.png'), 'Resolution', 150);
close(f);

fprintf('\n[Option 1] Unmanaged charging load by fleet size (depot %.0f kW):\n', depot_kw);
for i = 1:3
    fprintf('   %3d vehicles: peak %5.1f kW | energy %6.1f kWh/day | completion %5.1f%%\n', ...
        fleets(i), R.peak_kw(i), R.energy_kwh(i), 100 * R.completion(i));
end
end
