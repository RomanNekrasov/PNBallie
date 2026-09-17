<template>
  <span class="crown-icon" aria-label="Nummer één" role="img">
    <img :src="crownUrl" alt="" draggable="false" />
  </span>
</template>

<script setup lang="ts">
import crownUrl from '../assets/game3d/dominant.webp'
</script>

<style scoped>
.crown-icon {
  display: block;
  aspect-ratio: 1;
  pointer-events: none;
  filter: drop-shadow(0 2px 1px rgba(0, 0, 0, 0.55));
}

.crown-icon img {
  display: block;
  width: 100%;
  height: 100%;
  object-fit: contain;
}
</style>
