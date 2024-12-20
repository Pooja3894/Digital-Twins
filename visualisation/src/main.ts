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


/** Sets up and mounts Vue app to #app element */
import Vue from 'vue';
import VueRouter from "vue-router";
import BootstrapVue from "bootstrap-vue";

import App from '@/App.vue'
import routes from "@/routes";

import 'bootstrap/dist/css/bootstrap.css'
import 'bootstrap-vue/dist/bootstrap-vue.css'

import "@/assets/base-style.css"

// Set plugins
Vue.use(VueRouter);
Vue.use(BootstrapVue);

Vue.config.productionTip = false;

const router = new VueRouter({
  routes,
  mode: 'history'
});

new Vue({
  router,
  render: h => h(App)
}).$mount('#app');
