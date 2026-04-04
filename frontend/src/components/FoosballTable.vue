<template>
  <svg
    viewBox="0 0 400 700"
    class="w-full h-full"
    preserveAspectRatio="xMidYMid meet"
    xmlns="http://www.w3.org/2000/svg"
  >
    <!-- Table border -->
    <rect x="30" y="20" width="340" height="660" rx="16" fill="#2d6a30" stroke="#5a3a1a" stroke-width="8" />

    <!-- Field lines -->
    <line x1="30" y1="350" x2="370" y2="350" stroke="rgba(255,255,255,0.25)" stroke-width="2" />
    <circle cx="200" cy="350" r="50" fill="none" stroke="rgba(255,255,255,0.25)" stroke-width="2" />
    <text x="200" y="354" text-anchor="middle" font-size="14" font-weight="bold" fill="rgba(255,255,255,0.08)" font-family="'Barlow Condensed', system-ui, sans-serif" letter-spacing="3">PNBallie</text>

    <!-- Top goal area -->
    <rect x="130" y="20" width="140" height="60" rx="4" fill="none" stroke="rgba(255,255,255,0.25)" stroke-width="2" />
    <rect x="160" y="20" width="80" height="30" rx="2" fill="none" stroke="rgba(255,255,255,0.25)" stroke-width="2" />

    <!-- Bottom goal area -->
    <rect x="130" y="620" width="140" height="60" rx="4" fill="none" stroke="rgba(255,255,255,0.25)" stroke-width="2" />
    <rect x="160" y="650" width="80" height="30" rx="2" fill="none" stroke="rgba(255,255,255,0.25)" stroke-width="2" />

    <!-- Ball -->
    <circle cx="200" cy="350" r="5" fill="#f5f5f0" opacity="0.6" class="ball" />

    <!-- Rods + Players -->

    <!-- Blue keeper (1) — y=100 -->
    <line x1="10" y1="100" x2="390" y2="100" stroke="#8B7355" stroke-width="4" stroke-linecap="round" />
    <circle cx="200" cy="100" r="8" fill="#2d5fa1" stroke="#1e4a80" stroke-width="2" :class="{ wiggle: wiggle === 'blue' }" />

    <!-- Blue defense (2) — y=170 -->
    <line x1="10" y1="170" x2="390" y2="170" stroke="#8B7355" stroke-width="4" stroke-linecap="round" />
    <circle cx="150" cy="170" r="8" fill="#2d5fa1" stroke="#1e4a80" stroke-width="2" :class="{ wiggle: wiggle === 'blue' }" />
    <circle cx="250" cy="170" r="8" fill="#2d5fa1" stroke="#1e4a80" stroke-width="2" :class="{ wiggle: wiggle === 'blue' }" />

    <!-- Orange attack (3) — y=240 -->
    <line x1="10" y1="240" x2="390" y2="240" stroke="#8B7355" stroke-width="4" stroke-linecap="round" />
    <circle cx="130" cy="240" r="8" fill="#e87d2f" stroke="#c46a28" stroke-width="2" :class="{ wiggle: wiggle === 'orange' }" />
    <circle cx="200" cy="240" r="8" fill="#e87d2f" stroke="#c46a28" stroke-width="2" :class="{ wiggle: wiggle === 'orange' }" />
    <circle cx="270" cy="240" r="8" fill="#e87d2f" stroke="#c46a28" stroke-width="2" :class="{ wiggle: wiggle === 'orange' }" />

    <!-- Blue midfield (5) — y=310 -->
    <line x1="10" y1="310" x2="390" y2="310" stroke="#8B7355" stroke-width="4" stroke-linecap="round" />
    <circle cx="80" cy="310" r="8" fill="#2d5fa1" stroke="#1e4a80" stroke-width="2" :class="{ wiggle: wiggle === 'blue' }" />
    <circle cx="140" cy="310" r="8" fill="#2d5fa1" stroke="#1e4a80" stroke-width="2" :class="{ wiggle: wiggle === 'blue' }" />
    <circle cx="200" cy="310" r="8" fill="#2d5fa1" stroke="#1e4a80" stroke-width="2" :class="{ wiggle: wiggle === 'blue' }" />
    <circle cx="260" cy="310" r="8" fill="#2d5fa1" stroke="#1e4a80" stroke-width="2" :class="{ wiggle: wiggle === 'blue' }" />
    <circle cx="320" cy="310" r="8" fill="#2d5fa1" stroke="#1e4a80" stroke-width="2" :class="{ wiggle: wiggle === 'blue' }" />

    <!-- Orange midfield (5) — y=380 -->
    <line x1="10" y1="380" x2="390" y2="380" stroke="#8B7355" stroke-width="4" stroke-linecap="round" />
    <circle cx="80" cy="380" r="8" fill="#e87d2f" stroke="#c46a28" stroke-width="2" :class="{ wiggle: wiggle === 'orange' }" />
    <circle cx="140" cy="380" r="8" fill="#e87d2f" stroke="#c46a28" stroke-width="2" :class="{ wiggle: wiggle === 'orange' }" />
    <circle cx="200" cy="380" r="8" fill="#e87d2f" stroke="#c46a28" stroke-width="2" :class="{ wiggle: wiggle === 'orange' }" />
    <circle cx="260" cy="380" r="8" fill="#e87d2f" stroke="#c46a28" stroke-width="2" :class="{ wiggle: wiggle === 'orange' }" />
    <circle cx="320" cy="380" r="8" fill="#e87d2f" stroke="#c46a28" stroke-width="2" :class="{ wiggle: wiggle === 'orange' }" />

    <!-- Blue attack (3) — y=450 -->
    <line x1="10" y1="450" x2="390" y2="450" stroke="#8B7355" stroke-width="4" stroke-linecap="round" />
    <circle cx="130" cy="450" r="8" fill="#2d5fa1" stroke="#1e4a80" stroke-width="2" :class="{ wiggle: wiggle === 'blue' }" />
    <circle cx="200" cy="450" r="8" fill="#2d5fa1" stroke="#1e4a80" stroke-width="2" :class="{ wiggle: wiggle === 'blue' }" />
    <circle cx="270" cy="450" r="8" fill="#2d5fa1" stroke="#1e4a80" stroke-width="2" :class="{ wiggle: wiggle === 'blue' }" />

    <!-- Orange defense (2) — y=520 -->
    <line x1="10" y1="520" x2="390" y2="520" stroke="#8B7355" stroke-width="4" stroke-linecap="round" />
    <circle cx="150" cy="520" r="8" fill="#e87d2f" stroke="#c46a28" stroke-width="2" :class="{ wiggle: wiggle === 'orange' }" />
    <circle cx="250" cy="520" r="8" fill="#e87d2f" stroke="#c46a28" stroke-width="2" :class="{ wiggle: wiggle === 'orange' }" />

    <!-- Orange keeper (1) — y=590 -->
    <line x1="10" y1="590" x2="390" y2="590" stroke="#8B7355" stroke-width="4" stroke-linecap="round" />
    <circle cx="200" cy="590" r="8" fill="#e87d2f" stroke="#c46a28" stroke-width="2" :class="{ wiggle: wiggle === 'orange' }" />

    <!-- Rod handles (left) -->
    <rect x="2" y="94" width="18" height="12" rx="4" fill="#6B5B45" />
    <rect x="2" y="164" width="18" height="12" rx="4" fill="#6B5B45" />
    <rect x="2" y="234" width="18" height="12" rx="4" fill="#6B5B45" />
    <rect x="2" y="304" width="18" height="12" rx="4" fill="#6B5B45" />
    <rect x="2" y="374" width="18" height="12" rx="4" fill="#6B5B45" />
    <rect x="2" y="444" width="18" height="12" rx="4" fill="#6B5B45" />
    <rect x="2" y="514" width="18" height="12" rx="4" fill="#6B5B45" />
    <rect x="2" y="584" width="18" height="12" rx="4" fill="#6B5B45" />

    <!-- Rod handles (right) -->
    <rect x="380" y="94" width="18" height="12" rx="4" fill="#6B5B45" />
    <rect x="380" y="164" width="18" height="12" rx="4" fill="#6B5B45" />
    <rect x="380" y="234" width="18" height="12" rx="4" fill="#6B5B45" />
    <rect x="380" y="304" width="18" height="12" rx="4" fill="#6B5B45" />
    <rect x="380" y="374" width="18" height="12" rx="4" fill="#6B5B45" />
    <rect x="380" y="444" width="18" height="12" rx="4" fill="#6B5B45" />
    <rect x="380" y="514" width="18" height="12" rx="4" fill="#6B5B45" />
    <rect x="380" y="584" width="18" height="12" rx="4" fill="#6B5B45" />
  </svg>
</template>

<script setup lang="ts">
defineProps<{
  wiggle?: 'orange' | 'blue' | null
}>()
</script>

<style scoped>
.wiggle {
  animation: wiggle 0.4s ease-in-out 3;
  transform-box: fill-box;
  transform-origin: center;
}

@keyframes wiggle {
  0%, 100% { transform: translateX(0); }
  25% { transform: translateX(-4px); }
  75% { transform: translateX(4px); }
}

.ball {
  animation: ball-float 3s ease-in-out infinite;
}

@keyframes ball-float {
  0%, 100% { transform: translateY(0); }
  50% { transform: translateY(-2px); }
}
</style>
