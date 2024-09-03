/** Sets up and mounts Vue app to #app element */
import { createApp } from "vue";
import { createRouter, createWebHistory } from "vue-router";
import "bootstrap";
import App from "@/App.vue";
import routes from "@/routes";

import "bootstrap/dist/css/bootstrap.css";
import "@/assets/base-style.css";
import "@/assets/map-page.css";

const router = createRouter({
  routes,
  history: createWebHistory(import.meta.env.BASE_URL),
});

const app = createApp(App);

app.use(router);

app.mount("#app");
