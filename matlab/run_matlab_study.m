function run_matlab_study()
% RUN_MATLAB_STUDY  Master script for the MATLAB/Simulink layer of the project.
%   Runs the four-part study on the project's REAL data and saves all figures +
%   a summary to ../outputs/matlab/:
%     Option 1  Charging-load simulation across fleet sizes
%     Option 2  LP smart-charging optimisation (cost + peak)
%     Option 3  Solar + battery energy management
%     Option 4  Simulink digital twin + validation against Option 3
%
%   Run from MATLAB:   >> cd matlab; run_matlab_study
%   Or headless:       matlab -batch "cd('matlab'); run_matlab_study"

here = fileparts(mfilename('fullpath'));
addpath(here);
outdir = fullfile(fileparts(here), 'outputs', 'matlab');
if ~exist(outdir, 'dir'); mkdir(outdir); end

fprintf('======================================================================\n');
fprintf(' MATLAB / SIMULINK STUDY  -  Solar e-micromobility charging hub\n');
fprintf(' (operational layer; complements the Python robust-sizing layer)\n');
fprintf('======================================================================\n');

D  = load_project_data();
fprintf('Real data loaded: PV %.0f kWh/kWp/yr, mean trip %.2f km, %.2f kWh/vehicle/day\n', ...
    sum(D.pv_per_kwp), D.trip_dist_km, D.kwh_per_vehicle_day);

R1 = opt1_fleet_load(D, outdir);
R2 = opt2_smart_charging_lp(D, outdir);
R3 = opt3_solar_battery_ems(D, R2.smart_profile, outdir);
R4 = opt4_simulink_twin(D, R2.smart_profile, R3, outdir);

% ---- summary file -----------------------------------------------------------
fid = fopen(fullfile(outdir, 'matlab_summary.txt'), 'w');
fprintf(fid, 'MATLAB/SIMULINK STUDY SUMMARY\n');
fprintf(fid, '=============================\n\n');
fprintf(fid, 'Option 1 - fleet-size charging load (depot 60 kW):\n');
for i = 1:numel(R1.fleets)
    fprintf(fid, '  %3d vehicles: peak %.1f kW, energy %.1f kWh/day, completion %.1f%%\n', ...
        R1.fleets(i), R1.peak_kw(i), R1.energy_kwh(i), 100*R1.completion(i));
end
fprintf(fid, '\nOption 2 - LP smart charging (%d vehicles):\n', R2.N);
fprintf(fid, '  peak %.1f -> %.1f kW (-%.0f%%); cost GBP%.2f -> GBP%.2f (-%.0f%%)\n', ...
    R2.unmanaged_peak_kw, R2.smart_peak_kw, R2.peak_reduction_pct, ...
    R2.unmanaged_cost, R2.smart_cost, R2.cost_reduction_pct);
fprintf(fid, '\nOption 3 - solar+battery EMS (%d kWp, %d kWh):\n', R3.pv_kwp, R3.batt_kwh);
fprintf(fid, '  solar fraction %.0f%%, grid import %.1f kWh/day\n', ...
    100*R3.solar_fraction, R3.grid_import_kwh);
fprintf(fid, '\nOption 4 - Simulink digital twin validation:\n');
fprintf(fid, '  max SoC error vs MATLAB EMS: %.3f kWh (%.2f%%); grid error %.2f%%\n', ...
    R4.max_soc_err_kwh, R4.max_soc_err_pct, R4.grid_err_pct);
fclose(fid);

fprintf('\n----------------------------------------------------------------------\n');
fprintf('DONE. Figures + summary in: %s\n', outdir);
end
