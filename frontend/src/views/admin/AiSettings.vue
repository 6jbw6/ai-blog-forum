<template>
  <div class="ai-settings-page">
    <div class="page-title-row">
      <div>
        <h2 class="title">AI智能体配置</h2>
      </div>
    </div>

    <div class="settings-grid">
      <!-- 大模型接入策略卡片 -->
      <div class="setting-card">
        <el-form :model="configForm" label-position="top">
          <el-form-item label="自定义接入商名称">
            <el-input
              v-model="configForm.provider"
              placeholder="请输入接入商名称，例如：魔芯科技 / DeepSeek / SiliconFlow / OpenAI / 阿里云百炼"
              clearable
            />
          </el-form-item>

          <el-row :gutter="16">
            <el-col :span="12">
              <el-form-item label="API Base URL 端点">
                <el-input
                  v-model="configForm.base_url"
                  placeholder="例如：https://www.moxin.studio/v1 或 https://api.deepseek.com/v1"
                  clearable
                />
              </el-form-item>
            </el-col>
            <el-col :span="12">
              <el-form-item label="大模型 API Key">
                <el-input
                  v-model="configForm.api_key"
                  type="password"
                  show-password
                  placeholder="请输入接入商提供的 API Key (sk-...)"
                  clearable
                />
              </el-form-item>
            </el-col>
          </el-row>

          <el-form-item label="模型选择">
            <div class="model-select-row">
              <el-select
                v-model="configForm.model"
                filterable
                allow-create
                default-first-option
                placeholder="请选择或输入模型标识（可点击右侧拉取）"
                class="model-select"
                :loading="fetchingModels"
              >
                <el-option
                  v-for="item in availableModels"
                  :key="item"
                  :label="item"
                  :value="item"
                />
              </el-select>
              <el-button
                type="primary"
                plain
                :disabled="fetchingModels"
                @click="() => handleFetchModels(false)"
                title="向 Base URL 端点拉取当前支持的模型列表"
              >
                <el-icon :class="{ 'is-spinning': fetchingModels }"><Refresh /></el-icon>
                <span>拉取模型列表</span>
              </el-button>
            </div>
          </el-form-item>
        </el-form>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, watch, onMounted, onUnmounted } from 'vue'
import { ElMessage } from 'element-plus'
import { Refresh } from '@element-plus/icons-vue'
import { getAiConfigApi, updateAiConfigApi, fetchModelsApi } from '@/api/ai'
import type { LlmConfig } from '@/types'

const saving = ref(false)
const fetchingModels = ref(false)
const availableModels = ref<string[]>([])

const configForm = ref<LlmConfig>({
  provider: '自定义接入商',
  api_key: '',
  base_url: 'https://www.moxin.studio/v1',
  model: '[次]deepseek-v4-flash',
  top_k: 4,
  similarity_threshold: 0.18
})

const handleFetchModels = async (silent = false) => {
  if (!configForm.value.base_url) {
    if (!silent) ElMessage.warning('请先填写 API Base URL 端点')
    return
  }
  fetchingModels.value = true
  try {
    const models = await fetchModelsApi({
      base_url: configForm.value.base_url,
      api_key: configForm.value.api_key
    })
    if (Array.isArray(models) && models.length > 0) {
      availableModels.value = models
      if (!silent) {
        ElMessage.success(`成功拉取到 ${models.length} 个可用模型`)
      }
      // 如果当前未选择模型，自动将第一个设为默认值
      if (!configForm.value.model && models.length > 0) {
        configForm.value.model = models[0]
      }
    } else {
      if (!silent) ElMessage.warning('端点返回的模型列表为空')
    }
  } catch (err: any) {
    if (!silent) {
      ElMessage.error(err.message || '拉取模型列表失败，请检查 Base URL 与 API Key 是否有效')
    }
  } finally {
    fetchingModels.value = false
  }
}

const loadConfig = async () => {
  try {
    const conf = await getAiConfigApi()
    if (conf) {
      configForm.value = conf
      if (conf.model && !availableModels.value.includes(conf.model)) {
        availableModels.value.push(conf.model)
      }
      // 自动静默拉取一次当前端点的可用模型列表供下拉选取
      if (conf.base_url) {
        handleFetchModels(true)
      }
    }
  } catch (e) {
    console.warn('获取 AI 配置失败:', e)
  }
}

const saveConfig = async (silent = false) => {
  saving.value = true
  try {
    await updateAiConfigApi(configForm.value)
    if (!silent) {
      ElMessage.success('大模型与 RAG 运行时配置已成功更新！')
    }
  } catch (e: any) {
    if (!silent) {
      ElMessage.error(e?.message || '配置保存失败')
    }
  } finally {
    saving.value = false
  }
}

// —— 实时自动保存：输入停顿 800ms 后自动提交，无需手动点保存 ——
// 配置加载完成前不启用（避免初始回填触发保存回环）
const configLoaded = ref(false)
let autoSaveTimer: number | undefined

watch(
  configForm,
  () => {
    if (!configLoaded.value) return
    window.clearTimeout(autoSaveTimer)
    autoSaveTimer = window.setTimeout(() => {
      saveConfig(true)
    }, 800)
  },
  { deep: true }
)

onMounted(async () => {
  await loadConfig()
  configLoaded.value = true
})

onUnmounted(() => {
  window.clearTimeout(autoSaveTimer)
})
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

.subtitle {
  margin: 4px 0 0 0;
  font-size: 0.85rem;
  color: #71717a;
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

.model-select-row {
  display: flex;
  gap: 10px;
  align-items: center;
  width: 100%;
}

.model-select {
  flex: 1;
}

.is-spinning {
  animation: spin-refresh 0.9s linear infinite;
}

@keyframes spin-refresh {
  from {
    transform: rotate(0deg);
  }
  to {
    transform: rotate(360deg);
  }
}

.field-hint {
  font-size: 0.78rem;
  color: #71717a;
  margin-top: 6px;
  line-height: 1.4;
}

.sub-title {
  margin: 1.5rem 0 1rem 0;
  font-size: 0.95rem;
  font-weight: 700;
  color: #18181b;
}

.card-submit-row {
  margin-top: 1.5rem;
}
</style>
