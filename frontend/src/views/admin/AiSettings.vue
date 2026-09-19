<template>
  <div class="ai-settings-page">
    <div class="page-title-row">
      <div>
        <h2 class="title">AI 算法引擎与大模型中枢配置</h2>
        <p class="subtitle">统一管理自定义大模型接入端点、在线拉取模型列表、配置向量检索超参数及知识库全量索引重构</p>
      </div>
    </div>

    <div class="settings-grid">
      <!-- 大模型接入策略卡片 -->
      <div class="setting-card">
        <h3 class="card-title">自定义大模型服务接入</h3>
        <p class="card-desc">
          本系统基于标准 OpenAI 兼容协议构建，支持任意云端或私有化大模型服务（如魔芯科技、DeepSeek、SiliconFlow、OpenAI、阿里云百炼等）。输入 Base URL 与 API Key 后可直接在线拉取可用模型列表。
        </p>

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
            <div class="field-hint">
              💡 填写 Base URL 与 API Key 后，点击「拉取模型列表」即可在线获取该接入商支持的所有模型标识供直接选择。
            </div>
          </el-form-item>

          <h4 class="sub-title">🎯 向量知识库检索超参数</h4>

          <el-form-item label="召回切片数量 (推荐 3~6)">
            <el-slider v-model="configForm.top_k" :min="1" :max="10" show-input />
          </el-form-item>

          <el-form-item label="相关度过滤阈值 (0.05 ~ 0.5)">
            <el-slider
              v-model="configForm.similarity_threshold"
              :min="0.05"
              :max="0.5"
              :step="0.01"
              show-input
            />
            <div class="field-hint">
              💡 该阈值为「词法融合相关度」（0.75 × TF-IDF 余弦 + 0.25 × 饱和 BM25）。
              实测相关查询落在 22%~41%，无关查询 0%~15%，建议保持 0.15~0.22。
            </div>
          </el-form-item>

          <div class="card-submit-row">
            <el-button type="primary" size="large" :loading="saving" @click="saveConfig">
              保存并热重载 AI 引擎配置
            </el-button>
          </div>
        </el-form>
      </div>

      <!-- 知识库向量重构操作卡片 -->
      <div class="setting-card">
        <h3 class="card-title">⚡ 知识库全量向量重构</h3>
        <p class="card-desc">
          当批量导入外部 Markdown 文档或调整分块大小后，点击下方按钮将全量重新切分博文并重建 TF-IDF 特征向量。
        </p>

        <div class="rag-pipeline-box">
          <h4 class="pipeline-title">知识库数据流管道:</h4>
          <ol class="pipeline-steps">
            <li><strong>Markdown 解析</strong>：提取多级标题与段落边界</li>
            <li><strong>标题感知递归切块</strong>：保留 60 字符重叠步长防语义断裂</li>
            <li><strong>TF-IDF 词法加权投影</strong>：生成 L2 归一化向量（含 IDF 降噪，维度上限 4096）</li>
            <li><strong>持久化写入</strong>：保存至 MySQL <code>article_chunks</code> 表</li>
          </ol>
        </div>

        <div class="reindex-action-wrap">
          <el-button
            type="warning"
            size="large"
            :loading="reindexing"
            @click="triggerReindexAll"
          >
            ⚡ 一键全量重建所有博文向量索引
          </el-button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { Refresh } from '@element-plus/icons-vue'
import { getAiConfigApi, updateAiConfigApi, reindexAllApi, fetchModelsApi } from '@/api/ai'
import type { LlmConfig } from '@/types'

const saving = ref(false)
const reindexing = ref(false)
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

const saveConfig = async () => {
  saving.value = true
  try {
    await updateAiConfigApi(configForm.value)
    ElMessage.success('大模型与 RAG 运行时配置已成功更新！')
  } finally {
    saving.value = false
  }
}

const triggerReindexAll = async () => {
  reindexing.value = true
  try {
    const res = await reindexAllApi()
    ElMessage.success(`全量重构完成！成功索引 ${res.articles_indexed} 篇博文，共生成 ${res.total_chunks} 个向量知识切片！`)
  } catch (e) {
    ElMessage.error('重构失败')
  } finally {
    reindexing.value = false
  }
}

onMounted(() => {
  loadConfig()
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
  grid-template-columns: 1.25fr 1fr;
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

.rag-pipeline-box {
  background: #f4f4f5;
  border: 1px dashed #e4e4e7;
  border-radius: 10px;
  padding: 1.25rem;
  margin-bottom: 2rem;
}

.pipeline-title {
  margin: 0 0 8px 0;
  font-size: 0.9rem;
  font-weight: 700;
  color: #18181b;
}

.pipeline-steps {
  margin: 0;
  padding-left: 20px;
  display: flex;
  flex-direction: column;
  gap: 6px;
  font-size: 0.82rem;
  color: #52525b;
}

.reindex-action-wrap {
  text-align: center;
  padding: 1rem 0;
}
</style>
