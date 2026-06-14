function D = load_project_data()
% LOAD_PROJECT_DATA  Load the project's datasets for the MATLAB study.
%   Reads the same data the Python pipeline uses (UoW Bikes shared e-bike demand,
%   real PVGIS solar for Coventry) so the MATLAB and Python layers share one
%   source of truth.
%
%   Returns struct D with:
%     D.pv_per_kwp   8760x1 hourly PV yield per kWp (real PVGIS, Coventry/Warwick)
%     D.trip_dist_km mean trip distance from the UoW Bikes data
%     D.fleet_dft    mean available fleet (e-bikes) in the UoW Bikes data
%     D.avail24      24x1 fraction of the fleet at the hub each hour
%     D.tou24        24x1 time-of-use tariff (GBP/kWh)
%     D.wh_per_km, D.trips_per_day, D.grid_kw, D.bay_kw, D.eta_rt  (assumptions)

here = fileparts(mfilename('fullpath'));
root = fileparts(here);
dataDir = fullfile(root, 'data');

pv = readtable(fullfile(dataDir, 'pvgis_warwick_hourly.csv'));
D.pv_per_kwp = pv.pv_kWh_per_kWp(:);
if numel(D.pv_per_kwp) ~= 8760
    D.pv_per_kwp = D.pv_per_kwp(1:8760);
end

dft = readtable(fullfile(dataDir, 'uow_bikes_demand.csv'));
D.trip_dist_km = mean(dft.avg_trip_distance_km, 'omitnan');
D.fleet_dft    = mean(dft.fleet_size, 'omitnan');

% Vehicle availability at the hub (out on the street by day, back overnight)
D.avail24 = [0.95 0.95 0.95 0.95 0.95 0.92 0.85 0.65 0.45 0.30 0.25 0.25 ...
             0.25 0.25 0.30 0.40 0.55 0.70 0.82 0.90 0.93 0.95 0.95 0.95]';

% Time-of-use commercial tariff (UK Power Networks shape), GBP/kWh
D.tou24 = [0.16 0.16 0.16 0.16 0.16 0.16 0.22 0.26 0.26 0.26 0.26 0.26 ...
           0.26 0.26 0.26 0.26 0.38 0.38 0.38 0.28 0.24 0.22 0.18 0.16]';

% Engineering assumptions (shared e-bike / e-cargo fleet)
D.wh_per_km     = 22;      % fleet-mean energy intensity (Wh/km, e-bike + e-cargo)
D.trips_per_day = 4.0;     % trips per deployed bike per day (busy day, High scenario)
D.grid_kw       = 15;      % constrained grid connection (kW)
D.bay_kw        = 3.0;     % per charge-bay power (kW, low-power AC)
D.eta_rt        = 0.92;    % battery round-trip efficiency
D.dod           = 0.90;    % usable depth of discharge

% Per-bike daily charging energy (kWh). The trips x distance x Wh/km figure is
% modest for a single e-bike; the hub serves a MIXED fleet (e-bike ~0.4,
% e-cargo ~1.0 kWh/day), so we use a fleet-mean daily charge.
D.kwh_trips_based     = D.trips_per_day * D.trip_dist_km * D.wh_per_km / 1000;
D.kwh_per_vehicle_day = 0.5;   % mixed-fleet mean daily charge energy (kWh)
end
