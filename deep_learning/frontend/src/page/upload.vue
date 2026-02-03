<script setup lang="ts">
import {computed, ref} from "vue"
import  axios,  {type AxiosResponse} from "axios";
import  {useMessage, type UploadFileInfo } from 'naive-ui'
import {APIs} from "../utils.ts"

const message = useMessage()


interface ModelType  {
    email: string| null,
    description: string| null,
    file: UploadFileInfo | null,
}

const model = ref<ModelType>({
  email: null,
  description: null,
  file: null,
})


const emailStatus = computed(()=>{
  if (model.value.email === '' || model.value.email === null || model.value.email === undefined) {
    return ''
  }

  const re = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
  return re.test(model.value.email) ? "success" : "error"
})
const descriptionStatus = computed(()=>{
  if (model.value.description === '' || model.value.description === null) {
    return ''
  }

  return "success"
})

const disabled = computed(()=>{
  return model.value.email === null || model.value.description === null || model.value.file == null
})


function handleValidateClick(e: MouseEvent) {
  e.preventDefault()

  if (model.value.email !== null && model.value.description !== null && model.value.file !== null) {
    const formData = new FormData()
    formData.append('email', model.value.email)
    formData.append('description', model.value.description)
    formData.append('file', model.value.file)

    if (model.value.file.size > 500 * 1024 * 1024) {
      message.error("The upload file size > 500MB")
    }

    axios.post(APIs.upload, formData, {}).then((resp: AxiosResponse) => {
      message.success(resp.data)
    })
  }


}
</script>

<template>
  <n-grid x-gap="10" y-gap="10" cols="1">
    <n-gi span="1">
      <n-card hoverable>
        <n-text>
          Please upload your data along with a description and contact information to help us build better models.
        </n-text>
      </n-card>
      <n-divider />
      <n-card>
        <n-form
            label-placement="left"
            label-width="auto"
            require-mark-placement="right-hanging"
        >
          <n-form-item label="Email"  path="email">
            <n-input v-model:value="model.email" clearable :status="emailStatus" />
          </n-form-item>
          <n-form-item label="Description" path="description">
            <n-input type="textarea" v-model:value="model.description" clearable :status="descriptionStatus" />
          </n-form-item>
          <n-form-item label="Upload">
            <n-upload :max=1 @change="(info: any) => {model.file = info.file}">
              <n-button>Upload file</n-button>
              <n-text> <= 500 MB </n-text>
            </n-upload>
          </n-form-item>
          <n-form-item>
            <n-button attr-type="button" @click="handleValidateClick" :disabled="disabled" type="info">
              Submit
            </n-button>

          </n-form-item>
        </n-form>
      </n-card>
    </n-gi>
  </n-grid>

</template>

<style scoped>

</style>