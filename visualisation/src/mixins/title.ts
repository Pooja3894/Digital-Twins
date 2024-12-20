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


// Mixin to append title of a component to the base title of the app and makes this the document title.
// Best to only use this once per page.

import Vue from "vue";

/** The base title of the application, displayed in the document title */
export const appBaseTitle = "Flood Resilience Digital Twin (FReDT)";

export default {
  /**
   * Changes the document title prefix to the page title
   */
  created: function (this: Vue): void {
    const pageTitle = this.$options.title;
    if (pageTitle) {
      document.title = `${pageTitle} | ${appBaseTitle}`;
    }
  }
};
