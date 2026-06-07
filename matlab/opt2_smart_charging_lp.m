function R = opt2_smart_charging_lp(D, outdir)
% OPT2_SMART_CHARGING_LP  Smart-charging optimisation via linear programming.
%   Callable with NO arguments — data and output directory are set automatically.
%   Also callable from run_matlab_study: R2 = opt2_smart_charging_lp(D, outdir)

% ---- auto-load defaults when called with no arguments -----------------------
if nargin < 1 || isempty(D)
    fprintf('[Option 2] No data struct supplied — calling load_project_data()...\n');
    D = load_project_data();
end
if nargin < 2 || isempty(outdir)
    here   = fileparts(mfilename('fullpath'));
    outdir = fullfile(here, '..', 'outputs', 'matlab');
    if ~exist(outdir, 'dir'); mkdir(outdir); end
end

% ---- LP smart-charging ------------------------------------------------------
N      = 200;                                  % depot fleet for the LP demo
E      = N * D.kwh_per_vehicle_day;            % daily energy to deliver (kWh)
depot_kw = 20 * D.bay_kw;                      % installed bays power
cap    = min(D.avail24 * depot_kw, D.grid_kw); % grid-limited hourly charging cap
tou    = D.tou24;

% UNMANAGED baseline: "dumb" charge-on-arrival
arr = [0.01 0.01 0.01 0.01 0.01 0.01 0.02 0.02 0.02 0.02 0.02 0.02 ...
       0.02 0.02 0.03 0.05 0.10 0.14 0.16 0.13 0.09 0.06 0.04 0.02]';
arr = arr / sum(arr);
um  = E * arr;
um_cost = sum(tou .* um);
um_peak = max(um);

% SMART schedule: linprog  min  tou'*x + lambda*p
%   s.t.  sum(x)=E,  0<=x<=cap,  x<=p (peak tracker)
lambda = 0.5;
f   = [tou; lambda];
Aeq = [ones(1, 24), 0];
beq = E;
A   = [eye(24), -ones(24, 1)];
b   = zeros(24, 1);
lb  = [zeros(24, 1); 0];
ub  = [cap; inf];
opts = optimoptions('linprog', 'Display', 'none');
[z, ~, flag] = linprog(f, A, b, Aeq, beq, lb, ub, opts);
if flag ~= 1
    warning('linprog did not converge (flag %d); using capped uniform fallback', flag);
    x_fb = min(cap, E / 24 * ones(24, 1));
    z    = [x_fb; max(x_fb)];
end
x       = z(1:24);
sm_cost = sum(tou .* x);
sm_peak = max(x);

R.N                   = N;
R.energy_kwh          = E;
R.unmanaged_peak_kw   = um_peak;
R.smart_peak_kw       = sm_peak;
R.unmanaged_cost      = um_cost;
R.smart_cost          = sm_cost;
R.peak_reduction_pct  = 100 * (um_peak - sm_peak) / um_peak;
R.cost_reduction_pct  = 100 * (um_cost - sm_cost) / um_cost;
R.smart_profile       = x;
R.unmanaged_profile   = um;

% ---- plot -------------------------------------------------------------------
hours = (0:23)';
f1 = figure('Visible', 'off', 'Position', [100 100 900 460]);
yyaxis left
b1 = bar(hours, [um, x], 'grouped'); grid on;
b1(1).FaceColor = [0.88 0.21 0.09];
b1(2).FaceColor = [0.26 0.67 0.55];
ylabel('Charging load (kW)');
yyaxis right
plot(hours, tou, '-k', 'LineWidth', 1.6);
ylabel('Tariff (GBP/kWh)');
ax = gca; ax.YAxis(2).Color = 'k';
xlabel('Hour of day');
title(sprintf('Option 2 — LP smart charging: peak -%.0f%%, cost -%.0f%%', ...
    R.peak_reduction_pct, R.cost_reduction_pct));
legend({'Unmanaged', 'Smart (LP optimal)', 'ToU tariff'}, 'Location', 'northwest');
xlim([0 23]);
exportgraphics(f1, fullfile(outdir, 'matlab_opt2_smart_charging.png'), 'Resolution', 150);
close(f1);

fprintf('\n[Option 2] LP smart charging (%d vehicles, %.0f kWh/day):\n', N, E);
fprintf('   Peak  : unmanaged %.1f kW -> smart %.1f kW  (-%.0f%%)\n', ...
    um_peak, sm_peak, R.peak_reduction_pct);
fprintf('   Cost  : unmanaged GBP%.2f -> smart GBP%.2f  (-%.0f%%)\n', ...
    um_cost, sm_cost, R.cost_reduction_pct);
end
