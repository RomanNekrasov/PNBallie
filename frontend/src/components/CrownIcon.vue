<template>
  <svg class="crown-icon" aria-label="Nummer één" viewBox="0 0 32 24" role="img">
    <path d="M3 7.5 10 13l6-10 6 10 7-5.5-2.7 12H5.7L3 7.5Z" />
    <path class="crown-band" d="M6 18h20v4H6z" />
    <circle cx="3" cy="6.5" r="2" />
    <circle cx="16" cy="2.5" r="2" />
    <circle cx="29" cy="6.5" r="2" />
  </svg>
</template>

<style scoped>
.crown-icon {
  overflow: visible;
  fill: #ffd35a;
  stroke: #7c4500;
  stroke-width: 1.5;
  stroke-linejoin: round;
  filter: drop-shadow(0 2px 1px rgba(0, 0, 0, 0.55));
}

.crown-band {
  fill: #f4a51d;
}
</style>
