<template>
  <div class="ai-settings-page">
    <div class="page-title-row">
      <div>
        <h2 class="title">AI智能体配置</h2>
      </div>
    </div>

    <div class="settings-grid">
      <!-- 自定义模型卡片 -->
      <div class="setting-card">
        <h3 class="card-title">自定义模型</h3>
        <p class="card-desc">添加兼容 OpenAI / Anthropic 协议的自定义模型，连通性测试通过后将自动启用该模型。</p>

        <el-form label-position="top">
          <el-form-item label="API 格式" required>
            <el-select v-model="dialogForm.api_format" class="w-full">
              <el-option
                v-for="opt in API_FORMAT_OPTIONS"
                :key="opt.value"
                :label="opt.label"
                :value="opt.value"
              />
            </el-select>
          </el-form-item>

          <el-form-item>
            <template #label>
              <div class="label-row">
                <span class="label-text"><span class="label-star">*</span>自定义请求地址</span>
                <span class="full-url-toggle">
                  <el-icon><Link /></el-icon>
                  <span>完整 URL</span>
                  <el-switch v-model="dialogForm.full_url" size="small" />
                </span>
              </div>
            </template>
            <el-input v-model="dialogForm.base_url" placeholder="例如 https://api.openai.com/v1" clearable />
            <div class="field-hint">{{ urlHint }}</div>
          </el-form-item>

          <el-form-item label="模型 ID" required>
            <el-input v-model="dialogForm.model_id" placeholder="输入模型 ID" clearable />
          </el-form-item>

          <el-form-item label="API 密钥" required>
            <el-input v-model="dialogForm.api_key" type="password" show-password placeholder="请输入 API Key" clearable />
          </el-form-item>

          <el-collapse v-if="customModels.length" v-model="addedOpen" class="added-collapse">
            <el-collapse-item name="list">
              <template #title>
                <span class="added-collapse-title">已添加模型 ({{ customModels.length }})</span>
              </template>
              <div
                v-for="m in sortedCustomModels"
                :key="m.id"
                class="added-model-row"
                :class="{ 'is-active': isActive(m) }"
                title="点击启用该模型"
                @click="activateModel(m)"
              >
                <span class="added-model-active-dot"></span>
                <span class="added-model-name">{{ modelLabel(m) }}</span>
                <span class="added-model-actions">
                  <span v-if="isActive(m)" class="added-model-badge">使用中</span>
                  <el-icon class="added-model-del" title="删除该自定义模型" @click.stop="removeCustom(m)"><Delete /></el-icon>
                </span>
              </div>
            </el-collapse-item>
          </el-collapse>

          <div class="card-footer-row">
            <div class="footer-hint">
              <el-icon><InfoFilled /></el-icon>
              <span>连通性测试会发起一次真实请求，会消耗少量模型Token</span>
            </div>
            <div class="footer-btns">
              <el-button @click="resetDialogForm">重置</el-button>
              <el-button type="primary" :loading="adding" @click="submitCustomModel">添加模型</el-button>
            </div>
          </div>
        </el-form>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch, nextTick, onMounted, onUnmounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Delete, Link, InfoFilled } from '@element-plus/icons-vue'
import {
  getAiConfigApi,
  updateAiConfigApi,
  getCustomModelsApi,
  addCustomModelApi,
  deleteCustomModelApi
} from '@/api/ai'
import type { LlmConfig, CustomModelCreate, CustomModelItem, ApiFormat } from '@/types'

const customModels = ref<CustomModelItem[]>([])

// 主配置仅作内部载体：保存时携带启动侧 provider/base_url/key/RAG 参数与当前启用模型
const configForm = ref<LlmConfig>({
  provider: '自定义接入商',
  api_key: '',
  base_url: '',
  model: '',
  top_k: 4,
  similarity_threshold: 0.18
})

// —— 自定义模型表单 ——
const API_FORMAT_OPTIONS: { value: ApiFormat; label: string }[] = [
  { value: 'openai-chat', label: 'OpenAI Chat Completions 格式' },
  { value: 'openai-responses', label: 'OpenAI Responses API 格式' },
  { value: 'anthropic', label: 'Anthropic Messages 格式' }
]

const adding = ref(false)
const dialogForm = ref<CustomModelCreate>(defaultDialogForm())

function defaultDialogForm(): CustomModelCreate {
  return {
    api_format: 'openai-chat',
    base_url: '',
    full_url: false,
    model_id: '',
    display_name: '',
    api_key: '',
    temperature: 0.7
  }
}

const urlHint = computed(() => {
  if (dialogForm.value.full_url) {
    return '已开启完整 URL：请求地址将被原样使用，请自行带上协议路径（如 /chat/completions）。'
  }
  const suffix =
    dialogForm.value.api_format === 'anthropic'
      ? '/v1/messages'
      : dialogForm.value.api_format === 'openai-responses'
        ? '/responses'
        : '/chat/completions'
  return `请填写兼容 OpenAI API 的服务端点地址，不要以斜杠结尾。${suffix} 将会被补充到你填写的地址末尾。`
})

const modelLabel = (m: CustomModelItem) => m.display_name || m.model_id

// 已添加模型：启用的排最上面，其余按添加顺序
const addedOpen = ref(['list'])
const isActive = (m: CustomModelItem) => configForm.value.model === modelLabel(m)
const sortedCustomModels = computed(() => {
  const active = customModels.value.filter((m) => isActive(m))
  const rest = customModels.value.filter((m) => !isActive(m))
  return [...active, ...rest]
})

// 点击模型行即启用：热切换到其专属端点 / 密钥 / 协议
const activateModel = async (m: CustomModelItem) => {
  if (isActive(m)) return
  syncingConfig = true
  configForm.value.model = modelLabel(m)
  await nextTick()
  syncingConfig = false
  try {
    await updateAiConfigApi(configForm.value)
    ElMessage.success(`已启用 ${modelLabel(m)}`)
  } catch (err: any) {
    if (!err?.toastShown) ElMessage.error(err.message || '启用失败')
  }
}

const resetDialogForm = () => {
  dialogForm.value = defaultDialogForm()
}

const loadCustomModels = async () => {
  try {
    const list = await getCustomModelsApi()
    customModels.value = Array.isArray(list) ? list : []
  } catch (e) {
    console.warn('获取自定义模型列表失败:', e)
  }
}

const submitCustomModel = async () => {
  const f = dialogForm.value
  if (!f.base_url.trim()) {
    ElMessage.warning('请填写自定义请求地址')
    return
  }
  if (!f.model_id.trim()) {
    ElMessage.warning('请填写模型 ID')
    return
  }
  if (!f.api_key.trim()) {
    ElMessage.warning('请填写 API 密钥')
    return
  }

  adding.value = true
  try {
    const list = await addCustomModelApi({
      api_format: f.api_format,
      base_url: f.base_url.trim(),
      full_url: f.full_url,
      model_id: f.model_id.trim(),
      api_key: f.api_key.trim(),
      temperature: f.temperature
    })
    customModels.value = Array.isArray(list) ? list : []
    await loadConfig()
    resetDialogForm()
    ElMessage.success('连通性测试通过，已添加并启用该模型')
  } catch (err: any) {
    // 拦截器已弹过原始错误提示（如 401 详情），这里仅兜底
    if (!err?.toastShown) ElMessage.error(err.message || '连通性测试失败，请检查地址 / 模型 ID / 密钥')
  } finally {
    adding.value = false
  }
}

const removeCustom = async (m: CustomModelItem) => {
  try {
    await ElMessageBox.confirm(
      `确定删除自定义模型「${modelLabel(m)}」吗？若它是正在使用的模型，将自动回退到默认端点。`,
      '删除自定义模型',
      { confirmButtonText: '删除', cancelButtonText: '取消', type: 'warning' }
    )
  } catch {
    return
  }
  try {
    const list = await deleteCustomModelApi(m.id)
    customModels.value = Array.isArray(list) ? list : []
    await loadConfig()
    ElMessage.success('已删除')
  } catch (err: any) {
    if (!err?.toastShown) ElMessage.error(err.message || '删除失败')
  }
}

let syncingConfig = false

const loadConfig = async () => {
  try {
    const conf = await getAiConfigApi()
    if (conf) {
      syncingConfig = true
      configForm.value = conf
      // 等 deep watch 回调（flush: pre）在下一拍跑完再解除抑制，避免加载即触发一次保存
      await nextTick()
      syncingConfig = false
    }
  } catch (e) {
    console.warn('获取 AI 配置失败:', e)
  }
  await loadCustomModels()
}

const saveConfig = async (silent = false) => {
  try {
    await updateAiConfigApi(configForm.value)
    if (!silent) {
      ElMessage.success('大模型与 RAG 运行时配置已成功更新！')
    }
  } catch (e: any) {
    if (!silent) {
      ElMessage.error(e?.message || '配置保存失败')
    }
  }
}

// —— 自动保存：切换「当前使用模型」后直接生效（无需手动保存）——
// 配置加载完成前不启用（避免初始回填触发保存回环）
const configLoaded = ref(false)

watch(
  configForm,
  () => {
    if (!configLoaded.value || syncingConfig) return
    saveConfig(true)
  },
  { deep: true }
)

onMounted(async () => {
  await loadConfig()
  configLoaded.value = true
})

onUnmounted(() => {})
</script>

<style scoped>
.ai-settings-page {
  padding-bottom: 2rem;
}

.page-title-row {
  margin-bottom: 1.5rem;
}

.title {
  margin: 0;
  font-size: 1.4rem;
  font-weight: 700;
  color: #18181b;
}

.settings-grid {
  display: grid;
  grid-template-columns: 1fr;
  gap: 1.5rem;
}

.setting-card {
  background: #ffffff;
  border-radius: 14px;
  padding: 1.75rem;
  border: 1px solid #e4e4e7;
}

.card-title {
  margin: 0 0 8px 0;
  font-size: 1.15rem;
  font-weight: 700;
  color: #18181b;
}

.card-desc {
  font-size: 0.85rem;
  color: #71717a;
  line-height: 1.5;
  margin: 0 0 1.5rem 0;
}

.added-collapse {
  margin-top: 1.25rem;
  border-top: 1px solid #f4f4f5;
  border-bottom: none;
}

.added-collapse :deep(.el-collapse-item__header) {
  border-bottom: none;
}

.added-collapse :deep(.el-collapse-item__wrap) {
  border-bottom: none;
}

.added-collapse :deep(.el-collapse-item__content) {
  padding-bottom: 0;
}

.added-collapse-title {
  font-size: 0.85rem;
  font-weight: 700;
  color: #52525b;
}

.added-model-row {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 8px 12px;
  width: 100%;
  border: 1px solid #f4f4f5;
  border-radius: 8px;
  margin-bottom: 6px;
  cursor: pointer;
  transition: all 0.2s;
}

.added-model-row:hover {
  border-color: #10b981;
}

.added-model-row.is-active {
  border-color: #10b981;
  background: #ecfdf5;
}

.added-model-active-dot {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: #d4d4d8;
  flex-shrink: 0;
}

.added-model-row.is-active .added-model-active-dot {
  background: #10b981;
}

.added-model-name {
  flex: 1;
  min-width: 0;
  font-size: 0.85rem;
  font-weight: 600;
  color: #18181b;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.added-model-actions {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-shrink: 0;
}

.added-model-badge {
  font-size: 0.7rem;
  font-weight: 700;
  color: #059669;
  background: #ffffff;
  border: 1px solid #a7f3d0;
  border-radius: 9999px;
  padding: 1px 8px;
  white-space: nowrap;
}

.added-model-del {
  color: #a1a1aa;
  cursor: pointer;
  transition: color 0.2s;
}

.added-model-del:hover {
  color: #dc2626;
}

.w-full {
  width: 100%;
}

.label-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  width: 100%;
}

/* 必填星号：更醒目的正红 */
.setting-card :deep(.el-form-item.is-required > .el-form-item__label::before) {
  color: #dc2626;
  font-weight: 700;
}

/* label 占满整行，使「完整 URL」开关被推到行末 */
.setting-card :deep(.el-form-item__label) {
  width: 100%;
}

.label-star {
  color: #dc2626;
  font-weight: 700;
  margin-right: 4px;
}

.full-url-toggle {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-size: 0.82rem;
  font-weight: 600;
  color: #52525b;
}

.field-hint {
  font-size: 0.78rem;
  color: #a1a1aa;
  line-height: 1.5;
  margin-top: 6px;
  width: 100%;
}

.card-footer-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-top: 1.25rem;
  padding-top: 1rem;
  border-top: 1px solid #f4f4f5;
}

.footer-hint {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 0.78rem;
  color: #a1a1aa;
  text-align: left;
}

.footer-btns {
  display: flex;
  gap: 10px;
}
</style>
