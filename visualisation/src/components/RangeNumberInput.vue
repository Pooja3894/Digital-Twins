<!--Copyright © 2021-2024 Geospatial Research Institute Toi Hangarau-->
<!--LICENSE: https://github.com/GeospatialResearch/Digital-Twins/blob/master/LICENSE-->

<!--This program is free software: you can redistribute it and/or modify-->
<!--it under the terms of the GNU Affero General Public License as-->
<!--published by the Free Software Foundation, either version 3 of the-->
<!--License, or (at your option) any later version.-->

<!--This program is distributed in the hope that it will be useful,-->
<!--but WITHOUT ANY WARRANTY; without even the implied warranty of-->
<!--MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the-->
<!--GNU Affero General Public License for more details.-->

<!--You should have received a copy of the GNU Affero General Public License-->
<!--along with this program.  If not, see <http://www.gnu.org/licenses/>.-->

<template>
  <!-- Number input that can't accept values outside of the min<=value<=max range, reverting to the nearest valid value -->
  <input
    :value="model"
    type="number"
    @change="preventOutOfRange"
    :min="min"
    :max="max"
  >
</template>

<script lang="ts">
import {defineComponent} from "vue";

export default defineComponent({
  name: "RangeNumberInput",

  props: {
    // Current value of the input.
    value: {
      type: Number,
      required: true
    },
    // Minimum bound for the input.
    min: {
      type: Number,
      required: true
    },
    // Maximum bound for the input.
    max: {
      type: Number,
      required: true
    },
  },

  data() {
    return {
      // Internal value that can temporarily be out of range before updating.
      model: this.value
    }
  },

  methods: {
    /**
     * Intercepts Change events to ensure the target value is within it's minimum and maximum values.
     * Modifies the target value to achieve this.
     * @param event : Event The Change event from the input element.
     * */
    preventOutOfRange(event: Event) {
      const target = event.target as HTMLInputElement;
      const targetValue = parseFloat(target.value);

      // If value out of range, reset to nearest valid value.
      if (targetValue < parseFloat(target.min)) {
        target.value = target.min;
      } else if (targetValue > parseFloat(target.max)) {
        target.value = target.max;
      }
      this.model = parseFloat(target.value);
      // Emit js event for reactivity.
      this.$emit('input', this.model)
    }
  },

});
</script>
