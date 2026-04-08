<script setup lang="ts">
import axios, {AxiosError, type AxiosResponse} from "axios";
import { useMessage, type CountdownInst } from "naive-ui";
import { CloudDownloadOutlined } from '@vicons/material'

import { APIs } from "../utils.ts"
import { inject, onMounted, ref, watch } from "vue";

const state = inject('sharedState');
const message = useMessage()
const showError = (error: AxiosError) => {
    if (error.response !== undefined && error.response.data !== null) {
      message.error(String(error.response.data))
    }
}
const countdown = ref<CountdownInst | null>(null)
const startCountDown = ref<Boolean>(true)

// generate job status
const statusTag = (status: string) => {
  if (status === "completed") {
    return "success"
  }
  if (status === "failed") {
    return "error"
  }
  if (status === 'running') {
    return "info"
  }
  return "default"
}

// save log
const saveTextAsFile = () => {
  if (state.status === null){
    return
  }
  // 1. 创建 Blob 对象
  let blob = new Blob(
      [JSON.stringify(state.status, null, 4)],
      { type: 'text/plain;charset=utf-8' }
  );

  // 2. 创建临时 URL
  const url = URL.createObjectURL(blob);

  // 3. 创建 <a> 元素并触发下载
  const a = document.createElement('a');
  a.href = url;
  a.download = state.status.id + ".json"; // 指定文件名
  document.body.appendChild(a);
  a.click();

  // 4. 清理（释放内存）
  setTimeout(() => {
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  }, 100);
}


const downloadResults = () => {
  window.open(`${APIs.download}/${state.task_id}`, '_blank')
}


const getJobStatus = () => {
  countdown.value?.reset()
  if (state.task_id !== null && state.task_id !== undefined) {
    state.status = null
    axios.get(`${APIs.status}/${state.task_id}`).then((response: AxiosResponse) => {
      state.status = response.data
    }).catch((error: AxiosError) => {
      showError(error)
      state.status = null
    }).finally(() => {
      // 每次请求后，检查任务是否完成，决定是否继续请求
       if (
           state.status !== null &&
           state.status.status !== 'completed' &&
           state.status.status !== 'failed'
       ) {
        // 如果没有实现则继续拉取
        setTimeout(getJobStatus, 5000)
      }
    })
  } else {
    setTimeout(getJobStatus, 5000)
  }
}

watch(() => state.task_id, () => {getJobStatus()})
onMounted(() => getJobStatus())

</script>

<template>
  <n-flex justify="space-around" style="margin-right: 10px">
    <n-card title="Task" v-if="state.status !== null">
      <n-descriptions label-placement="top" :title="'ID: ' + state.status.id" :column="1">
        <n-descriptions-item label="Task category" >
          <n-tag :bordered="false" >
            {{ state.status.description }}
          </n-tag>
        </n-descriptions-item>
        <n-descriptions-item label="Task status">
          <n-tag :type="statusTag(state.status.status)" :bordered="false">
            {{ state.status.status }}
          </n-tag>
        </n-descriptions-item>
      </n-descriptions>

      <div v-if="state.status.status !== 'completed' && state.status.status !== 'failed'">
        <n-divider />
        Refresh in
        <n-countdown ref="countdown" :duration="5000" :active="startCountDown" />
        seconds
      </div>
      <n-divider />

      <n-collapse>
        <n-collapse-item title="Parameters" name="1">
          <n-descriptions label-placement="left" :column="1" bordered>
            <n-descriptions-item label="Gene">
              {{ state.status.parameters.gene }}
            </n-descriptions-item>
            <n-descriptions-item label="Genome">
              {{ state.status.parameters.genome }}
            </n-descriptions-item>
            <n-descriptions-item label="PAM">
              {{ state.status.parameters.pam }}
            </n-descriptions-item>
            <n-descriptions-item label="Genomic region" v-if="state.status.parameters.chromosome !== null">
              {{ state.status.parameters.chromosome }}:{{ state.status.parameters.start }}-{{ state.status.parameters.end }}
            </n-descriptions-item>
            <n-descriptions-item label="Max mismatch">
              {{ state.status.parameters.max_mismatch }}
            </n-descriptions-item>
            <n-descriptions-item label="Editing pattern">
              {{ state.status.parameters.editing_pattern }}
            </n-descriptions-item>
          </n-descriptions>
        </n-collapse-item>
        <n-collapse-item title="Logs" name="2">
          <n-timeline>
            <div v-for="row in state.status.progress" >
              <n-timeline-item :content="row" type="success" />
            </div>
            <div v-for="row in state.status.error" >
              <n-timeline-item :content="row" type="error" />
            </div>
          </n-timeline>
        </n-collapse-item>
      </n-collapse>

      <n-divider>Download</n-divider>

      <n-button-group>
        <n-button
            @click="downloadResults"
            small type="success"
            :disabled="state.status.status !== 'completed'"
        >
          <template #icon>
            <n-icon><CloudDownloadOutlined /></n-icon>
          </template>
          Results
        </n-button>

        <n-popover trigger="hover">
          <template #trigger>
            <n-button @click="saveTextAsFile" small>
              <template #icon>
                <n-icon><CloudDownloadOutlined /></n-icon>
              </template>
              Log
            </n-button>
          </template>
          <span>Please send this log to the maintainer if you have any questions about this prediction.</span>
        </n-popover>
      </n-button-group>
    </n-card>
  </n-flex>

</template>

<style scoped>

</style>