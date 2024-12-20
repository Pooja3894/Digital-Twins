// Copyright © 2021-2024 Geospatial Research Institute Toi Hangarau
// LICENSE: https://github.com/GeospatialResearch/Digital-Twins/blob/master/LICENSE
//
// This program is free software: you can redistribute it and/or modify
// it under the terms of the GNU Affero General Public License as
// published by the Free Software Foundation, either version 3 of the
// License, or (at your option) any later version.
//
// This program is distributed in the hope that it will be useful,
// but WITHOUT ANY WARRANTY; without even the implied warranty of
// MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
// GNU Affero General Public License for more details.
//
// You should have received a copy of the GNU Affero General Public License
// along with this program.  If not, see <http://www.gnu.org/licenses/>.

import {RouteConfig} from "vue-router";
import AboutPage from "@/pages/AboutPage.vue"
import LicensePage from "@/pages/LicensePage.vue"
import MapPage from "@/pages/MapPage.vue";

/**
 * Sets router url endpoints to specific pages
 */
const routes: RouteConfig[] = [
  {
    path: "/",
    name: "Map",
    component: MapPage
  },
  {
    path: "/about",
    name: "About",
    component: AboutPage
  },
  {
    path: "/license",
    name: "License",
    component: LicensePage
  },
  {
    path: '*',
    redirect: '/'
  }
];
export default routes;
