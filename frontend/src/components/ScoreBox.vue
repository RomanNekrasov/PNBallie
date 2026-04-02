<template>
  <div class="select-none rounded-2xl" :style="glassStyle">
    <!-- Touch: horizontal scroll-snap picker -->
    <div v-if="isTouch" class="relative">
      <div
        ref="scrollEl"
        class="flex overflow-x-auto snap-x snap-mandatory scrollbar-hide"
        :style="{ width: itemSize * 3 + 'px' }"
        @scroll="onScroll"
      >
        <!-- Spacer so first/last items can center -->
        <div :style="{ minWidth: itemSize + 'px' }" class="shrink-0" />
        <div
          v-for="n in 11"
          :key="n - 1"
          class="snap-center shrink-0 flex items-center justify-center text-white font-bold tabular-nums transition-all duration-150"
          :style="{ width: itemSize + 'px', height: itemSize + 'px', fontSize: '28px' }"
          :class="score === n - 1 ? 'opacity-100 scale-110' : 'opacity-30 scale-90'"
        >
          {{ n - 1 }}
        </div>
        <div :style="{ minWidth: itemSize + 'px' }" class="shrink-0" />
      </div>
      <!-- Fade edges -->
      <div class="pointer-events-none absolute inset-y-0 left-0 w-8 bg-gradient-to-r from-black/30 to-transparent rounded-l-2xl" />
      <div class="pointer-events-none absolute inset-y-0 right-0 w-8 bg-gradient-to-l from-black/30 to-transparent rounded-r-2xl" />
    </div>

    <!-- Non-touch: +/- buttons -->
    <div v-else class="flex items-center gap-1 px-3 py-2">
      <button
        @click="$emit('adjust', -1)"
        class="w-11 h-11 rounded-full text-white text-2xl font-bold flex items-center justify-center active:scale-90 transition-transform"
      >
        &minus;
      </button>
      <span class="text-white text-3xl font-bold min-w-[2ch] text-center tabular-nums drop-shadow">{{ score }}</span>
      <button
        @click="$emit('adjust', 1)"
        class="w-11 h-11 rounded-full text-white text-2xl font-bold flex items-center justify-center active:scale-90 transition-transform"
      >
        +
      </button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, ref, onMounted, watch, nextTick } from 'vue'

const props = defineProps<{
  score: number
  team: 'orange' | 'blue'
}>()

const emit = defineEmits<{
  adjust: [delta: number]
  'update:score': [value: number]
}>()

const itemSize = 48
const scrollEl = ref<HTMLElement | null>(null)
const isTouch = ref(false)
let programmaticScroll = false

onMounted(() => {
  isTouch.value = window.matchMedia('(pointer: coarse)').matches
  nextTick(() => scrollToScore(props.score, false))
})

watch(() => props.score, (val) => {
  scrollToScore(val, true)
})

function scrollToScore(score: number, smooth: boolean) {
  if (!scrollEl.value) return
  programmaticScroll = true
  scrollEl.value.scrollTo({
    left: score * itemSize,
    behavior: smooth ? 'smooth' : 'instant',
  })
  setTimeout(() => { programmaticScroll = false }, 100)
}

let scrollTimeout: ReturnType<typeof setTimeout> | null = null

function onScroll() {
  if (programmaticScroll) return
  if (scrollTimeout) clearTimeout(scrollTimeout)
  scrollTimeout = setTimeout(() => {
    if (!scrollEl.value) return
    const newScore = Math.round(scrollEl.value.scrollLeft / itemSize)
    const clamped = Math.max(0, Math.min(10, newScore))
    if (clamped !== props.score) {
      emit('update:score', clamped)
    }
  }, 50)
}

const glassStyle = computed(() => {
  const color = props.team === 'orange' ? '217, 124, 46' : '45, 95, 161'
  return {
    background: `rgba(${color}, 0.45)`,
    backdropFilter: 'blur(16px) saturate(180%)',
    WebkitBackdropFilter: 'blur(16px) saturate(180%)',
    border: `1px solid rgba(${color}, 0.65)`,
    boxShadow: `0 4px 24px rgba(0,0,0,0.25), inset 0 1px 0 rgba(255,255,255,0.2)`,
  }
})
</script>

<style scoped>
.scrollbar-hide {
  -ms-overflow-style: none;
  scrollbar-width: none;
}
.scrollbar-hide::-webkit-scrollbar {
  display: none;
}
</style>
