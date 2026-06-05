function R = opt3_solar_battery_ems(D, smart_profile, outdir)
% OPT3_SOLAR_BATTERY_EMS  Solar + battery + charging-load energy management.
%   Adds a PV array and a battery to the smart charging load and runs an hourly
%   energy-management strategy (PV -> load -> battery -> grid), reporting solar
%   self-consumption, grid import and the battery state-of-charge profile.

pv_kwp   = 25;
batt_kwh = 30;
eta      = sqrt(D.eta_rt);          % one-way efficiency
usable   = batt_kwh * D.dod;
pmax     = batt_kwh * 0.5;          % 0.5C power limit

% Representative sunny summer day from the real PVGIS series (day ~183)
d0 = (183-1)*24 + 1;
pv_day = D.pv_per_kwp(d0:d0+23) * pv_kwp;     % kWh/h for the array
load   = smart_profile(:);                     % smart charging load (kWh/h)

soc = usable*0.5;
gridv = zeros(24,1); pv2load = zeros(24,1); bat2load = zeros(24,1);
pv2bat = zeros(24,1); curt = zeros(24,1); socv = zeros(24,1);
for h = 1:24
    g = pv_day(h); dmd = load(h);
    a = min(g, dmd); pv2load(h) = a; res = dmd - a; sur = g - a;   % PV -> load
    if sur > 0                                                     % surplus -> battery
        room = (usable - soc)/eta; c = min([sur, pmax, room]);
        soc = soc + c*eta; pv2bat(h) = c; sur = sur - c;
    end
    curt(h) = max(sur,0);
    if res > 0                                                     % deficit -> battery -> grid
        if soc > 0
            dis = min([res, pmax, soc*eta]); soc = soc - dis/eta;
            bat2load(h) = dis; res = res - dis;
        end
        gridv(h) = res;
    end
    socv(h) = soc;
end

served = sum(load);
R.solar_fraction = (sum(pv2load)+sum(bat2load)) / served;
R.grid_import_kwh = sum(gridv);
R.pv_kwp = pv_kwp; R.batt_kwh = batt_kwh;
R.soc = socv; R.pv2load = pv2load; R.bat2load = bat2load; R.gridv = gridv;

% ---- plot: stacked supply + SoC ---------------------------------------------
hours = (0:23)';
f = figure('Visible','off','Position',[100 100 900 460]);
yyaxis left
ar = area(hours, [pv2load, bat2load, gridv]); grid on;
ar(1).FaceColor=[0.95 0.72 0.02]; ar(2).FaceColor=[0.18 0.49 0.20]; ar(3).FaceColor=[0.64 0.23 0.45];
ylabel('Power to load (kW)');
yyaxis right
plot(hours, 100*socv/max(usable,eps), '--', 'Color',[0.10 0.10 0.23], 'LineWidth',2);
ylabel('Battery SoC (%)'); ylim([0 105]); ax=gca; ax.YAxis(2).Color=[0.10 0.10 0.23];
xlabel('Hour of day');
title(sprintf('Option 3 — Solar+battery EMS: solar fraction %.0f%% (%dkWp, %dkWh)', ...
    100*R.solar_fraction, pv_kwp, batt_kwh));
legend({'PV \rightarrow load','Battery \rightarrow load','Grid \rightarrow load','Battery SoC'}, 'Location','northwest');
xlim([0 23]);
exportgraphics(f, fullfile(outdir, 'matlab_opt3_solar_battery.png'), 'Resolution', 150);
close(f);

fprintf('\n[Option 3] Solar+battery energy management (%d kWp PV, %d kWh battery):\n', pv_kwp, batt_kwh);
fprintf('   Solar fraction %.0f%% | grid import %.1f kWh/day | battery cycles midday->evening\n', ...
    100*R.solar_fraction, R.grid_import_kwh);
end
