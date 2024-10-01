<template>
  <!-- Navigation Bar to allow switching between different pages in the app -->
  <div class="nav-bar">
    <div class="nav-bar-bcg-image">
      <img src="@/assets/kowhaiwhai.png" />
    </div>
    <nav class="navbar navbar-expand-lg">
      <div class="container-fluid">
        <router-link class="navbar-brand" :to="{ name: 'Map' }">
          Ōtākaro Digital Twin
        </router-link>
        <button
          class="navbar-toggler"
          type="button"
          data-bs-toggle="collapse"
          data-bs-target="#navbarText"
          aria-controls="navbarText"
          aria-expanded="false"
          aria-label="Toggle navigation"
        >
          <span class="navbar-toggler-icon"></span>
        </button>
        <div class="collapse navbar-collapse" id="navbarText">
          <ul class="navbar-nav me-auto mb-2 mb-lg-0">
            <li class="nav-item">
              <router-link class="nav-link" :to="{ name: 'Map' }">
                Map
              </router-link>
            </li>
            <li class="nav-item">
              <router-link class="nav-link" :to="{ name: 'About' }">
                About
              </router-link>
            </li>
            <li class="nav-item">
              <router-link class="nav-link" :to="{ name: 'License' }">
                License
              </router-link>
            </li>
          </ul>
        </div>
      </div>
    </nav>
  </div>
</template>

<script setup lang="ts"></script>

<style scoped></style>
