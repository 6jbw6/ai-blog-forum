<template>
  <el-dialog
    v-model="visible"
    title="裁剪头像"
    width="480px"
    align-center
    destroy-on-close
    append-to-body
    :close-on-click-modal="false"
    :lock-scroll="false"
    class="avatar-cropper-dialog"
  >
    <div class="cropper-body">
      <div
        ref="stageRef"
        class="crop-stage"
        :class="{ dragging: isDragging }"
        @pointerdown="onPointerDown"
        @pointermove="onPointerMove"
        @pointerup="onPointerUp"
        @pointercancel="onPointerUp"
        @wheel.prevent="onWheel"
      >
        <img v-if="imgUrl" :src="imgUrl" class="crop-img" :style="imgStyle" alt="待裁剪图片" draggable="false" />
        <div class="crop-mask"></div>
        <div v-if="!loaded" class="crop-loading">图片加载中...</div>
      </div>

      <div class="zoom-row">
        <span class="zoom-label">缩放</span>
        <el-slider v-model="zoomPercent" :disabled="!loaded" />
      </div>
    </div>

    <template #footer>
      <div class="dialog-footer">
        <el-button @click="visible = false">取消</el-button>
        <el-button type="primary" :disabled="!loaded" @click="confirmCrop">确认并上传</el-button>
      </div>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
import { ref, reactive, computed, watch, onBeforeUnmount } from 'vue'
import { ElMessage } from 'element-plus'

const props = defineProps<{ file: File | null }>()
const emit = defineEmits<{ (e: 'confirm', file: File): void }>()

const visible = defineModel<boolean>({ default: false })

// 舞台固定 320px 方形，裁剪输出 256×256（页面展示最大 64px，留足高清余量）
const STAGE_SIZE = 320
const OUTPUT_SIZE = 256
const ZOOM_STEP = 1.12

const stageRef = ref<HTMLDivElement>()
const imgUrl = ref('')
const isDragging = ref(false)

const loaded = computed(() => st.loaded)

const st = reactive({
  loaded: false,
  natW: 0,
  natH: 0,
  minScale: 0.1,
  maxScale: 4,
  scale: 1,
  x: 0,
  y: 0
})

let imgEl: HTMLImageElement | null = null
let panStart: { px: number; py: number; ox: number; oy: number } | null = null

const clamp = (v: number, lo: number, hi: number) => Math.min(hi, Math.max(lo, v))

// 图片必须始终铺满舞台（cover），圆圈内不会出现空白
const clampX = (v: number) => {
  const dispW = st.natW * st.scale
  if (dispW <= STAGE_SIZE) return (STAGE_SIZE - dispW) / 2
  return clamp(v, STAGE_SIZE - dispW, 0)
}
const clampY = (v: number) => {
  const dispH = st.natH * st.scale
  if (dispH <= STAGE_SIZE) return (STAGE_SIZE - dispH) / 2
  return clamp(v, STAGE_SIZE - dispH, 0)
}

const imgStyle = computed(() => ({
  width: `${st.natW * st.scale}px`,
  height: `${st.natH * st.scale}px`,
  transform: `translate(${st.x}px, ${st.y}px)`
}))

// 以 (cx, cy) 为锚点缩放：该点下的图像像素在缩放前后保持不动
const zoomAt = (nextScale: number, cx: number, cy: number) => {
  const s = clamp(nextScale, st.minScale, st.maxScale)
  if (s === st.scale) return
  const ix = (cx - st.x) / st.scale
  const iy = (cy - st.y) / st.scale
  st.scale = s
  st.x = clampX(cx - ix * s)
  st.y = clampY(cy - iy * s)
}

// 滑杆与 scale 采用对数映射，缩放手感均匀
const zoomPercent = computed({
  get: () => {
    const range = Math.log(st.maxScale / st.minScale) || 1
    return Math.round((Math.log(st.scale / st.minScale) / range) * 100)
  },
  set: (p: number) => {
    const s = st.minScale * Math.pow(st.maxScale / st.minScale, p / 100)
    zoomAt(s, STAGE_SIZE / 2, STAGE_SIZE / 2)
  }
})

const onWheel = (e: WheelEvent) => {
  if (!st.loaded) return
  const rect = stageRef.value?.getBoundingClientRect()
  if (!rect) return
  const factor = e.deltaY < 0 ? ZOOM_STEP : 1 / ZOOM_STEP
  zoomAt(st.scale * factor, e.clientX - rect.left, e.clientY - rect.top)
}

const onPointerDown = (e: PointerEvent) => {
  if (!st.loaded || panStart) return
  // 个别环境（如自动化注入的合成指针）setPointerCapture 会抛异常，不能让它中断拖动
  try {
    stageRef.value?.setPointerCapture(e.pointerId)
  } catch {
    /* ignore */
  }
  isDragging.value = true
  panStart = { px: e.clientX, py: e.clientY, ox: st.x, oy: st.y }
}

const onPointerMove = (e: PointerEvent) => {
  if (!panStart) return
  st.x = clampX(panStart.ox + (e.clientX - panStart.px))
  st.y = clampY(panStart.oy + (e.clientY - panStart.py))
}

const onPointerUp = () => {
  isDragging.value = false
  panStart = null
}

const initImage = (file: File) => {
  if (imgUrl.value) URL.revokeObjectURL(imgUrl.value)
  st.loaded = false
  imgEl = new Image()
  const url = URL.createObjectURL(file)
  imgUrl.value = url
  imgEl.onload = () => {
    if (!imgEl) return
    st.natW = imgEl.naturalWidth || 1
    st.natH = imgEl.naturalHeight || 1
    st.minScale = Math.max(STAGE_SIZE / st.natW, STAGE_SIZE / st.natH)
    st.maxScale = st.minScale * 5
    st.scale = st.minScale
    st.x = (STAGE_SIZE - st.natW * st.scale) / 2
    st.y = (STAGE_SIZE - st.natH * st.scale) / 2
    st.loaded = true
  }
  imgEl.onerror = () => {
    st.loaded = false
    ElMessage.error('图片加载失败，请换一张试试')
    visible.value = false
  }
  imgEl.src = url
}

watch(
  [visible, () => props.file],
  ([v, f]) => {
    if (v && f) initImage(f)
  }
)

const confirmCrop = () => {
  const img = imgEl
  if (!img || !st.loaded) return
  const canvas = document.createElement('canvas')
  canvas.width = OUTPUT_SIZE
  canvas.height = OUTPUT_SIZE
  const ctx = canvas.getContext('2d')
  if (!ctx) {
    ElMessage.error('当前浏览器不支持图片裁剪')
    return
  }
  // 把舞台区域（含圆形选区）映射回原图坐标裁出
  const sw = STAGE_SIZE / st.scale
  const sx = -st.x / st.scale
  const sy = -st.y / st.scale
  ctx.drawImage(img, sx, sy, sw, sw, 0, 0, OUTPUT_SIZE, OUTPUT_SIZE)
  canvas.toBlob(
    (blob) => {
      if (!blob) {
        ElMessage.error('头像裁剪失败，请重试')
        return
      }
      emit('confirm', new File([blob], 'avatar.png', { type: 'image/png' }))
    },
    'image/png'
  )
}

onBeforeUnmount(() => {
  if (imgUrl.value) URL.revokeObjectURL(imgUrl.value)
})
</script>

<style scoped>
.cropper-body {
  padding: 0 4px;
}

.crop-stage {
  position: relative;
  width: 320px;
  height: 320px;
  margin: 0 auto;
  background: #18181b;
  border-radius: 12px;
  overflow: hidden;
  cursor: grab;
  touch-action: none;
  user-select: none;
}

.crop-stage.dragging {
  cursor: grabbing;
}

.crop-img {
  position: absolute;
  top: 0;
  left: 0;
  transform-origin: 0 0;
  will-change: transform;
  pointer-events: none;
  -webkit-user-drag: none;
}

.crop-mask {
  position: absolute;
  inset: 12px;
  border-radius: 50%;
  border: 2px solid rgba(255, 255, 255, 0.85);
  box-shadow: 0 0 0 9999px rgba(24, 24, 27, 0.55);
  pointer-events: none;
}

.crop-loading {
  position: absolute;
  inset: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #d4d4d8;
  font-size: 0.85rem;
}

.zoom-row {
  display: flex;
  align-items: center;
  gap: 14px;
  padding: 0 8px 4px;
}

.zoom-label {
  font-size: 0.8rem;
  color: #52525b;
  white-space: nowrap;
}

.zoom-row :deep(.el-slider) {
  flex: 1;
}

.dialog-footer {
  display: flex;
  justify-content: flex-end;
  gap: 10px;
}
</style>

<style>
.avatar-cropper-dialog {
  max-width: 94vw;
}
</style>
