<template>
  <span class="stats-avatar" :style="avatarStyle">
    <CrownIcon v-if="crowned" class="stats-avatar-crown" />
    <img
      v-if="avatarUrl"
      :src="avatarUrl"
      :alt="`Avatar van ${name}`"
      draggable="false"
    />
    <span v-else class="stats-avatar-fallback">{{ initials }}</span>
  </span>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { playerAvatar, playerInitials } from '../playerAvatar'
import CrownIcon from './CrownIcon.vue'

const props = withDefaults(defineProps<{
  name: string
  size?: number
  crowned?: boolean
}>(), {
  size: 48,
  crowned: false,
})

const avatarUrl = computed(() => playerAvatar(props.name))
const initials = computed(() => playerInitials(props.name))
const avatarStyle = computed(() => ({
  width: `${props.size}px`,
  height: `${props.size}px`,
  '--crown-size': `${Math.round(props.size * 0.4)}px`,
  '--crown-top': `${Math.round(props.size * -0.24)}px`,
}))
</script>

<style scoped>
.stats-avatar {
  position: relative;
  flex: 0 0 auto;
  display: inline-grid;
  place-items: center;
  overflow: visible;
}

.stats-avatar img {
  width: 100%;
  height: 100%;
  object-fit: contain;
  object-position: center bottom;
  filter: drop-shadow(0 5px 5px rgba(0, 0, 0, 0.38));
}

.stats-avatar-fallback {
  width: 82%;
  height: 82%;
  display: grid;
  place-items: center;
  border: 2px solid #465469;
  border-radius: 50%;
  color: #f4f7fb;
  background: #273244;
  font: 800 0.34em/1 system-ui, sans-serif;
}

.stats-avatar-crown {
  position: absolute;
  z-index: 3;
  top: var(--crown-top);
  left: 50%;
  width: var(--crown-size);
  height: auto;
  transform: translateX(-50%) rotate(-7deg);
}
</style>
