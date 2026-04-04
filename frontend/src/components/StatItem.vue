<template>
  <div class="stat-tile">
    <div class="stat-label">{{ label }}</div>
    <div class="stat-value">{{ value }}</div>
    <div v-if="sub" class="stat-sub">{{ sub }}</div>
  </div>
</template>

<script setup lang="ts">
defineProps<{
  label: string
  value: string
  sub?: string
}>()
</script>

<style scoped>
.stat-tile {
  border-radius: 10px;
  padding: 10px 12px;
  background:
    linear-gradient(180deg, rgba(0, 0, 0, 0.2) 0%, rgba(0, 0, 0, 0.34) 100%),
    rgba(16, 34, 19, 0.48);
  border: 1px solid rgba(171, 133, 84, 0.34);
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.05);
}

.stat-label {
  font-size: 10px;
  color: rgba(243, 230, 214, 0.46);
  text-transform: uppercase;
  letter-spacing: 0.1em;
  margin-bottom: 3px;
}

.stat-value {
  font-size: 15px;
  font-weight: 600;
  color: #f3e7d1;
  line-height: 1.2;
}

.stat-sub {
  margin-top: 2px;
  font-size: 11px;
  color: rgba(243, 230, 214, 0.55);
}
</style>
