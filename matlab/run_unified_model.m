function run_unified_model()
% RUN_UNIFIED_MODEL  ONE integrated MATLAB/Simulink model of the solar
%   e-micromobility charging hub. It runs the four analyses as a single coupled
%   study on the project's REAL data and produces ONE combined dashboard figure
%   plus the individual figures:
%       (A) fleet-size charging-load simulation
%       (B) LP smart-charging optimisation (Optimization Toolbox)
%       (C) solar + battery energy management
%       (D) Simulink digital-twin validation
%
%   Run:  >> cd matlab; run_unified_model
%   Or:   matlab -batch "cd('matlab'); run_unified_model"

here = fileparts(mfilename('fullpath'));
addpath(here);
outdir = fullfile(fileparts(here), 'outputs', 'matlab');
if ~exist(outdir, 'dir'); mkdir(outdir); end

fprintf('======================================================================\n');
fprintf(' UNIFIED MATLAB/SIMULINK MODEL - solar e-micromobility charging hub\n');
fprintf('======================================================================\n');

D  = load_project_data();
R1 = opt1_fleet_load(D, outdir);
R2 = opt2_smart_charging_lp(D, outdir);
R3 = opt3_solar_battery_ems(D, R2.smart_profile, outdir);
R4 = opt4_simulink_twin(D, R2.smart_profile, R3, outdir);

% ===== combined 2x2 dashboard ============================================== %
hours = (0:23)';
f = figure('Visible','off','Position',[60 60 1180 760]);
tl = tiledlayout(f, 2, 2, 'TileSpacing','compact', 'Padding','compact');
title(tl, 'Unified model — solar e-micromobility charging hub (real data)', ...
    'FontWeight','bold', 'FontSize', 14);

% (A) fleet load
nexttile; hold on; grid on;
cols = [0.26 0.53 0.67; 0.95 0.59 0.12; 0.88 0.21 0.09];
for i = 1:3
    plot(hours, R1.profiles(:,i), '-o', 'LineWidth',1.8, 'Color',cols(i,:), ...
        'MarkerSize',3, 'DisplayName',sprintf('%d veh', R1.fleets(i)));
end
yline(R1.depot_kw, '--k', 'Depot cap');
title('(A) Fleet-size charging load'); xlabel('Hour'); ylabel('Load (kW)');
legend('Location','northwest','FontSize',7); xlim([0 23]);

% (B) LP smart charging
nexttile;
bar(hours, [R2.unmanaged_profile, R2.smart_profile], 'grouped'); grid on;
title(sprintf('(B) LP smart charging: peak -%.0f%%, cost -%.0f%%', ...
    R2.peak_reduction_pct, R2.cost_reduction_pct));
xlabel('Hour'); ylabel('Load (kW)');
legend({'Unmanaged','Smart (LP)'}, 'Location','northwest','FontSize',7); xlim([0 23]);
ax=gca; ax.Children(2).FaceColor=[0.88 0.21 0.09]; ax.Children(1).FaceColor=[0.26 0.67 0.55];

% (C) solar + battery EMS
nexttile;
yyaxis left
ar = area(hours, [R3.pv2load, R3.bat2load, R3.gridv]); grid on;
ar(1).FaceColor=[0.95 0.72 0.02]; ar(2).FaceColor=[0.18 0.49 0.20]; ar(3).FaceColor=[0.64 0.23 0.45];
ylabel('Power to load (kW)');
yyaxis right
plot(hours, 100*R3.soc/max(R3.soc), '--', 'Color',[0.10 0.10 0.23], 'LineWidth',1.8);
ylabel('SoC (%)'); ax=gca; ax.YAxis(2).Color=[0.10 0.10 0.23]; ylim([0 105]);
title(sprintf('(C) Solar+battery EMS: solar %.0f%%', 100*R3.solar_fraction));
xlabel('Hour'); xlim([0 23]);

% (D) digital-twin validation
nexttile; hold on; grid on;
plot(R4.t, 100*R4.soc_ml/R4.usable, '-o', 'LineWidth',2, 'Color',[0.10 0.10 0.23], ...
    'DisplayName','MATLAB EMS','MarkerSize',3);
plot(R4.t, 100*R4.soc_tw/R4.usable, '--s', 'LineWidth',1.6, 'Color',[0.18 0.49 0.20], ...
    'DisplayName','Simulink twin','MarkerSize',3);
title(sprintf('(D) Simulink digital twin (err %.2f%%)', R4.max_soc_err_pct));
xlabel('Hour'); ylabel('Battery SoC (%)'); legend('Location','best','FontSize',7); xlim([0 23]);

exportgraphics(f, fullfile(outdir, 'matlab_unified_dashboard.png'), 'Resolution', 150);
close(f);

% ===== unified summary ===================================================== %
fid = fopen(fullfile(outdir, 'matlab_summary.txt'), 'w');
fprintf(fid, 'UNIFIED MATLAB/SIMULINK MODEL - SUMMARY\n=======================================\n\n');
fprintf(fid, '(A) Fleet load: peak %.1f/%.1f/%.1f kW for %d/%d/%d vehicles\n', ...
    R1.peak_kw, R1.fleets);
fprintf(fid, '(B) LP smart charging: peak -%.0f%%, cost -%.0f%%\n', ...
    R2.peak_reduction_pct, R2.cost_reduction_pct);
fprintf(fid, '(C) Solar+battery EMS: solar fraction %.0f%%, grid %.1f kWh/day\n', ...
    100*R3.solar_fraction, R3.grid_import_kwh);
fprintf(fid, '(D) Simulink digital twin: validated to %.2f%% SoC error\n', R4.max_soc_err_pct);
fclose(fid);

fprintf('\n----------------------------------------------------------------------\n');
fprintf('UNIFIED MODEL DONE. Combined dashboard + 4 figures in: %s\n', outdir);
end
