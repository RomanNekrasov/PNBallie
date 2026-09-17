<template>
  <span v-if="winStreak >= 5" class="player-flames" role="img" :aria-label="`${winStreak} overwinningen op rij`" :data-win-streak="winStreak">
    <img v-for="side in ['left', 'right']" :key="side" :src="flameUrl" :class="['flame', `flame--${side}`]" alt="" draggable="false" />
  </span>
</template>

<script setup lang="ts">
import flameUrl from '../assets/game3d/streak_flame.webp'

withDefaults(defineProps<{ winStreak?: number }>(), { winStreak: 0 })
</script>

<style scoped>
.player-flames {
  position: absolute;
  z-index: 0;
  left: -17.5%;
  bottom: -3.5%;
  width: 135%;
  height: 115%;
  pointer-events: none;
  user-select: none;
  filter: drop-shadow(0 0 5px rgb(255 120 20 / 45%));
}
.flame {
  position: absolute;
  bottom: 0;
  width: 58%;
  height: 88%;
  object-fit: contain;
  object-position: center bottom;
  transform-origin: center bottom;
  animation: flame-sway 1.8s ease-in-out infinite alternate;
}
.flame--left { left: 2%; --lean: -6deg; }
.flame--right { right: 2%; --lean: 6deg; animation-delay: -.9s; }
@keyframes flame-sway {
  from { transform: rotate(var(--lean)) scale(.97, .96); opacity: .8; }
  to { transform: rotate(var(--lean)) scale(1, 1.03); opacity: .95; }
}
@media (prefers-reduced-motion: reduce) {
  .flame { animation: none; transform: rotate(var(--lean)); opacity: .9; }
}
</style>
