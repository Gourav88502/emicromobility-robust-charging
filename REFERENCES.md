# References & Data Sources

All quantitative assumptions in [`src/config.py`](src/config.py) trace to the sources below
(compiled from the approved Data Inventory, `data/data_inventory.xlsx`).

## Primary data

1. **Department for Transport (DfT)** — *Shared rental e‑scooter trials monitoring data, January 2022 to May 2024.* GOV.UK Open Data (Open Government Licence v3.0). Newcastle City Council / Neuron operator rows. https://www.gov.uk/government/statistics/monitoring-of-dft-funded-e-scooter-trials
2. **PVGIS — Photovoltaic Geographical Information System (EU JRC).** Solar radiation & PV performance, Newcastle (lat 54.978, lon −1.618), TMY. https://re.jrc.ec.europa.eu/pvg_tools/en/
3. **NASA POWER** — Prediction of Worldwide Energy Resources (validation). Parameter ALLSKY_SFC_SW_DWN. https://power.larc.nasa.gov/api/
4. **UK Carbon Intensity API (National Grid ESO).** Regional endpoint `/regional/regionid/13` (North East England). https://api.carbonintensity.org.uk/

## Solar PV & inverter performance

5. IEA PVPS Task 1 (2023). *Trends in Photovoltaic Applications.* IEA Photovoltaic Power Systems Programme. https://iea-pvps.org/trends_reports/
6. Fraunhofer ISE (2021). *Current and future cost of photovoltaics.* DOI: 10.24406/ise‑n‑643692.
7. SMA Solar Technology AG (2024). *Sunny Tripower CORE1 Inverter Datasheet.*
8. Pfenninger, S. & Staffell, I. (2016). *Long‑term patterns of European PV output…* Energy, 114, 1251–1265. DOI: 10.1016/j.energy.2016.08.060.

## Battery storage

9. IRENA (2017). *Electricity Storage and Renewables: Costs and Markets to 2030.* Abu Dhabi: IRENA.
10. BloombergNEF (2024). *Battery Price Survey 2024.*
11. Mongird, K. et al. (2020). *2020 Grid Energy Storage Technology Cost and Performance Assessment.* PNNL/DOE, PNNL‑28866.
12. Lith, A. et al. (2021). *Degradation mechanisms of lithium‑ion batteries: a state‑of‑the‑art review.* Journal of Power Sources, 490, 229517. DOI: 10.1016/j.jpowsour.2021.229517.

## EV / e‑scooter charge points

13. DfT / OZEV (2023). *Electric Vehicle Infrastructure Strategy.* UK Government.
14. Rolec EV (2024). *WallPod EV Charger Datasheet* (7 kW / 22 kW AC Type 2).
15. Pod Point (2024). *Solo 3 and Commercial Charging Product Guide.*
16. Kempower (2024). *Satellite Charger Datasheet.*
17. Zap‑Map (2024). *UK EV Charging Market Intelligence: Annual Report 2024.*

## Costs & tariffs

18. BEIS (2020). *Electricity Generation Costs 2020.* UK Department for Business, Energy & Industrial Strategy.
19. IRENA (2024). *Renewable Power Generation Costs in 2023.* Abu Dhabi: IRENA.
20. Solar Trade Association (2024). *Solar and Storage: State of the Market Report 2024.*
21. SSEN Distribution (2023). *EV and Renewable Energy Integration: Network Investment Planning Report.*
22. Ofgem — *Electricity tariff & market data.* https://www.ofgem.gov.uk/
23. UK Power Networks (2024). *Smart Tariff and Time‑of‑Use Pricing Data.*
24. Agora Energiewende (2023). *Future Cost of Electricity* (European price projections 2025–2035).

## E‑scooter energy use

25. Gössling, S. (2020). *Integrating e‑scooters in urban transportation…* Transportation Research Part D, 79, 102230. DOI: 10.1016/j.trd.2020.102230.
26. Hollingsworth, J. et al. (2019). *Life cycle assessment of the energy and environmental impacts of e‑scooter sharing.* Environmental Science & Technology Letters, 6(5), 279–285. DOI: 10.1021/acs.estlett.9b00141.

## Methodology — robust optimisation, stochastic programming, sensitivity

27. Ben‑Tal, A. & Nemirovski, A. (2009). *Robust Optimization.* Princeton University Press. ISBN 978‑0‑691‑14368‑1. *(minimax‑regret / maximin foundation)*
28. Birge, J.R. & Louveaux, F. (2011). *Introduction to Stochastic Programming* (2nd ed.). Springer. DOI: 10.1007/978‑1‑4614‑0237‑4. *(chance‑constrained stochastic program)*
29. Saltelli, A. et al. (2008). *Global Sensitivity Analysis: The Primer.* Wiley. ISBN 978‑0‑470‑05997‑5. *(tornado / OAT sensitivity)*

---
*Crown copyright data reused under the Open Government Licence v3.0. All other sources are cited for the assumptions they inform; no third‑party text or code is reproduced in this repository.*
