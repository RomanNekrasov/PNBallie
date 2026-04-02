<template>
  <div>
    <div class="flex items-center justify-between text-xs text-white/50 mb-1">
      <span>{{ label }}</span>
      <span>{{ orange }} - {{ blue }}</span>
    </div>
    <div class="flex h-4 rounded overflow-hidden bg-white/5">
      <div
        class="bg-[rgb(217,124,46)] transition-all"
        :style="{ width: orangePct }"
      ></div>
      <div
        class="bg-[rgb(45,95,161)] transition-all"
        :style="{ width: bluePct }"
      ></div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'

const props = defineProps<{
  label: string
  orange: number
  blue: number
}>()

const total = computed(() => props.orange + props.blue)
const orangePct = computed(() => total.value ? `${(props.orange / total.value) * 100}%` : '50%')
const bluePct = computed(() => total.value ? `${(props.blue / total.value) * 100}%` : '50%')
</script>
