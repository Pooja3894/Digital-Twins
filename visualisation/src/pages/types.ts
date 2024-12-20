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


// Adds additional type information for pages
import Vue from 'vue';

// Type augmentation on the Vue options API
declare module 'vue/types/options' {
  /* eslint-disable @typescript-eslint/no-unused-vars */ // Matching V extends Vue with type we are augmenting.
  interface ComponentOptions<V extends Vue> {
    /** Title option for a page, can be used with the title mixin */
    title?: string
  }
}
