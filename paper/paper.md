---
title: 'Flood Resilience Digital Twin: A system to enable flood risk analysis and prediction'
tags:
  - Python
  - flooding
  - hydrology
  - digital twin
  - resilience
  - disaster
  - hazard
  - risk assessment

authors:
  - name: Casey Li
    orcid: 0009-0009-1707-8289
    equal-contrib: true 
    affiliation: "1, 2"

  - name: Luke Parkinson
    orcid: 0000-0003-3130-3445
    equal-contrib: true 
    affiliation: 1
    
  - name: Xander Cai
    orcid: 0009-0008-9995-9778
    affiliation: 1
  
  - name: Martin Nguyen
    orcid: 0000-0003-4469-0149
    affiliation: 1

  - name: Matthew Wilson
    orcid: 0000-0001-9459-6981
    affiliation: 1
    
  - name: Greg Preston
    affiliation: 2
    
  - name: Rose Pearson
    orcid: 0000-0002-4700-2113
    affiliation: "1, 3"
    
  - name: Rob Deakin
    orcid: 0000-0001-7391-3052
    affiliation: 4
  
  - name: Emily Lane
    orcid: 0000-0002-9261-6640
    affiliation: 3
    
affiliations:
  - name: Geospatial Research Institute | Toi Hangarau, New Zealand
    index: 1
  - name: Building Innovation Partnership, New Zealand
    index: 2
  - name: National Institute of Water and Atmospheric Research, New Zealand
    index: 3
  - name: Land Information New Zealand | Toitū Te Whenua, New Zealand
    index: 4

date: 23 August 2024
bibliography: paper.bib
---

# Summary

The Flood Resilience Digital Twin (FReDT) is an open-source geospatial system to improve flood risk management in
Aotearoa New Zealand [@fredt]. Analysis for flood risk management requires processing large amounts of data to identify
risky areas or effects that inundation may cause to people, property and infrastructure.

FReDT simplifies this process by automatically ingesting data from external sources and producing data useful for
risk assessment and decision-making. The system comprises a processing server which handles the data ingestion and processing; and a front-end visualisation web
application for convenient
processing and visualisation control. The processing server can independently interact with the
front end using a web API, allowing other tools to programmatically interact with the digital twin to process new
scenarios or retrieve data. Information on how to run the web application and web API are both documented
in the project README.md [@fredt].

Flood analysts can select an area of interest and enter parameters such as sea level rise. FReDT will
produce a raster map of the maximum flood depth reached for each cell during the flood scenario, and highlight flooded buildings
that exceed a specified depth (default 0.1m).

Designing the digital twin, we utilised methods developed in another research program, the NIWA-led Mā te haumaru ō
te
wai^[https://niwa.co.nz/natural-hazards/research-projects/mā-te-haumaru-ō-te-wai-increasing-flood-resilience-across-aotearoa]
. To process elevation LiDAR point cloud data from LINZ into a form ready to use for modelling the flow of water over
the terrain surface we use GeoFabrics [@geofabrics]. These hydrologically-conditioned DEMs, along
with additional data sources such as rainfall estimation from NIWA's High-Intensity Rainfall Design System
(HIRDS)^[https://hirds.niwa.co.nz/] [@hirds] and flood statistics from their Flood Frequency
Tool^[https://niwa.maps.arcgis.com/apps/webappviewer/index.html?id=933e8f24fe9140f99dfb57173087f27d] [@flood-frequency1]
[@flood-frequency2] are used as inputs to the flood model. FReDT currently uses BG-Flood [@bg-flood] as the
underlying hydrodynamic flood model. BG-Flood was chosen because it aligns with Mā te haumaru
ō te wai and has support from the NIWA authors. Using methods developed for Mā te haumaru ō te wai, we will
share scenarios created in the digital twin with NIWA, and ingest scenarios created externally into our tool.

Improvements to FReDT are being considered which include UI upgrades and more options for data
visualisation to make it easier to use as a flood risk research tool. Other additions may include integration
 with the RiskScape model [@riskscape], allowing  damage and exposure estimation.

![Screenshot of a FReDT scenario, showing flooded areas with buildings highlighted in red if they are inundated.](Capture2024.png)

# External data inputs

The following shows data providers and datasets ingested by FReDT:

* LINZ
    * LiDAR Digital Surface Models
    * Digital Elevation Models (DEMs)
    * Building Outlines
    * Coastlines
    * Roads
* NIWA
    * Flood Frequency Statistics
    * High-Intensity Rainfall Design System
    * Tide
* Takiwā
    * Sea Level Rise
* OSM
    * Waterways
* StatsNZ
    * Region Geometries
* Ministry for the Environment
    * Sea Draining Catchments

# Data outputs

On the first scenario run for an area of interest, hydrologically conditioned DEMs are created from LiDAR data using the
GeoFabrics package [@geofabrics]. These are reused for subsequent scenarios until the LiDAR or other geospatial
input data are updated, in which case they are regenerated. These DEMs are generated using
the same process as the Mā te haumaru ō te wai flood research program. These form part of the inputs
for the BG Flood model, but can also be downloaded through the web API for further analysis.

On every scenario run, we create multiple data outputs specific to the scenario. Foremost is the flood
model output, created using the shallow water hydrodynamic model BG-Flood [@bg-flood] which models time-series
geospatial rasters of inundation depths, water surface elevation, ground surface elevation, and water flow velocities in
NetCDF format. In addition, we perform analysis incorporating building footprint data to create a building flood dataset that identifies buildings inundated past the chosen threshold.

# Statement of need

Flooding, is the most frequent, destructive, and expensive natural hazard in the
country [@ijerph18083952]. Worldwide, for the period of 1900-2015, hydrological disasters like floods and landslides
were responsible for approximately 21.5% of all natural disaster-related deaths [@guoqiang2019].

Floods are primarily caused by heavy or prolonged rainfall and can lead to direct and indirect damages to housing,
infrastructure, farmland, and the community. With approximately two-thirds of the population living in flood-prone
areas, and many towns and cities in the country built on floodplains, floods in New Zealand  have catastrophic
consequences [@ijerph18083952; @doi:10.1080/17477891.2022.2142500].

Recent flooding in New Zealand has resulted in significant property damage and economic loss, as
well as detrimental effects on household income, expenditure, consumption, and employment across the
country [@doi:10.1080/17477891.2022.2142500]. With the country’s extreme heavy rainfall events expected to increase in
frequency and sea level rise brought on by climate change, the risk of flooding is expected to escalate over the next
few decades [@collins2018; @serrao-neumann2024; @McDermott2022]. Effective communication and management of flood risks
are critical in mitigating flood impacts, and planning must take these growing risks into account.

In 2022, we conducted a workshop to review the needs of our key stakeholders, including  local
councils, utility companies, Crown Research Institutes, and other organisations interested in flood
management [@stormwater2022]. Flood risk managers identified that it was crucial to combine our tool 
into their existing toolsets of GIS software and data pipelines. Consequently, we designed an API 
that allows users to request data from the tool using Open Geospatial Consortium standards such as Web Feature Service.
This also allows downloading of the raw output files for direct analysis.
Early prototypes of FREDT were standalone applications but after this
workshop it can now be used standalone or as a data service to be used with other tooling.

Currently, a major challenge for flood risk management and mitigation is managing the substantial amounts of 
infrastructure and environmental spatial data. Acquiring and processing these data in a timely manner becomes a
formidable task for individuals or small teams, particularly  when the information needs to be
quickly compiled for rapid decision-making, resulting in high costs for developing suitable risk assessments
scenarios.

FReDT addresses these challenges by automating processes and integrating real-time data for analysis,
prediction, and visualization. This makes assessments more efficient and cost-effective, enabling the
exploration of hundreds or even thousands of scenarios. It also provides decision-makers with significantly more
detailed and comprehensive information, facilitating informed decisions.

# Acknowledgements

This project was funded by FrontierSI and the Building Innovation Partnership. We also received in-kind support from
NIWA and LINZ with project guidance and assistance with data and research needs. We would also like to thank Pooja
Khosla, for creating the first prototype of the FReDT.

# References
