<script setup lang="ts">
import axios, {AxiosError, type AxiosResponse} from "axios";
import {useMessage} from "naive-ui";
import {AddTaskFilled, ContentPasteSearchOutlined, DangerousOutlined } from '@vicons/material'

import { APIs } from "../utils.ts"
import type { FormData, SelectOption, State } from "../interfaces.ts"
import {computed, onMounted, ref, watch, inject} from "vue";

const state = inject<State>('sharedState');
const message = useMessage()

const formData = ref<FormData>({
  gene: null,
  genome_range: null,
  fasta: null,
  max_mismatch: 5,
  pam: "NTTM",
  genome: "hg38",
  editing_pattern: null,
  off_target: false
})
const off_target = ref(false)

const models = ref<SelectOption[]>([])
const genomes = ref<Selection[]>([])

const pam_rule = ref<string[]>(['A', 'T', 'C', 'G', 'N'])
const pam_input_status = ref<string>("")

const gene_input_loading = ref<Boolean>(false)
const gene_name = ref<String | null>(null)
const gene_name_status = ref<string>('')
const gene_candidate = ref<SelectOption[]>([])

const genomic_range_status = computed(() => {
  // update genomic region
  let value = formData.value.genome_range
  if (value === null) {
    return ''
  }

  let match = value.match(/(chr)?\w+:\d+-\d+/)
  if (match) {
    return "success"
  } else {
    return "error"
  }
})

const sequence = ref<string | null>(null)
const sequence_status = ref<string>('')
const sequence_status_message = ref<string>('Please enter sequences — one per line, or in FASTA format.')

const editing_pattern_status = computed(() => {
  let value = formData.value.editing_pattern
  if (value === null || value === '' || value === undefined) {
    return ''
  }

  if (isValidSequence(value)) {
    if (value.length == 20) {
      return "success"
    } else {
      return "warning"
    }
  } else {
    return "error"
  }
})

const activeTab = ref<string>('gene')

const showError = (error: AxiosError) => {
    if (error.response !== undefined && error.response.data !== null) {
      message.error(String(error.response.data))
    }
}

const examples = {
  "fasta": '>NC_000017.11_example\n'+
    'CTCAAAAGTCTAGAGCCACCGTCCAGGGAGCAGGTAGCTGCTGGGCTCCGGGGACACTTTGCGTTCGGGC\n'+
    'TGGGAGCGTGCTTTCCACGACGGTGACACGCTTCCCTGGATTGGGTAAGCTCCTGACTGAACTTGATGAG\n'+
    'TCCTCTCTGAGTCACGGGCTCTCGGCTCCGTGTATTTTCAGCTCGGGAAAATCGCTGGGGCTGGGGGTGG\n'+
    'GGCAGTGGGGACTTAGCGAGTTTGGGGGTGAGTGGGATGGAAGCTTGGCTAGAGGGATCATCATAGGAGT',
  "gene": {"label": "TP53 (ENSG00000141510.20)", "value": "ENSG00000141510.20"},
  "range": 'chr17:7668421-7687487'
}

// check the input PAM is invalid
const isValidSequence = (str: string) => {
  const validChars = new Set(pam_rule.value);
  return str.split('').every(char => validChars.has(char));
}

// check whether the input PAM sequence is valid
const checkInputPAM = (label: string, option: SelectOption) => {
  if (label === null || option.value === null) {
    formData.value.pam = null
    pam_input_status.value = ""
    return
  }

  if (label.length != 4) {
    pam_input_status.value = "warning"
    formData.value.pam = null
  }else if (isValidSequence(option.value)) {
    pam_input_status.value = "success"
    formData.value.pam = option.value
  } else {
    pam_input_status.value = "error"
    formData.value.pam = null
  }
}

// check whether the form is ready
const isFormValid = computed(() => {

  let status = formData.value.pam !== null && formData.value.genome !== null && (editing_pattern_status.value === '' || editing_pattern_status.value === 'success')
  // using different input type then using different checks

  if (activeTab.value === 'gene') {
    status = status && gene_name_status.value === 'success'
  }

  if (activeTab.value === 'genomic_range') {
    status = status && genomic_range_status.value === 'success'
  }

  if (activeTab.value === 'fasta') {
    status = status && sequence_status.value === 'success'
  }

  return status
})

// get the gene autocomplete information
const fetchGeneInfo = () => {
  if (
      gene_name.value !== null &&   // gene name should not be null
      gene_name.value.length > 2 &&  // the input character length should not be too short
      !gene_name.value.includes('(') // the input gene should not be chosen one
  ) {
    gene_input_loading.value = true
    axios.get(`${APIs.gene}/${formData.value.genome}/${gene_name.value}`).then((response: AxiosResponse) => {
      let res = []
      for (let row of response.data) {
        res.push({label: `${row.name} (${row.id})`, value: row.id})
      }
      gene_candidate.value = res
    }).catch((error: AxiosError) => {
      showError(error)
    }).finally(() => {
      gene_input_loading.value = false
    })
  } else if (gene_name.value !== null && gene_name.value.includes('(')) {
    // the gene is chosen, just reset the candidate list is fine
    gene_candidate.value = []
  } else {
    // reset the candidate list and status
    gene_name_status.value = ''
    gene_candidate.value = []
  }
  gene_candidate.value = []
}

// update gene name
const chooseGene = (value: string) => {
  gene_name_status.value = 'success'
  formData.value.gene = value
}

// update the input sequence
watch(sequence, () => {
  if (sequence_status.value === 'success' && sequence.value !== null) {
    let res = []
    if (!sequence.value.includes(">")) {
      let lines = sequence.value.trim().split(/\r?\n/).filter(line => line.trim() !== '');
      for (let i = 0; i < lines.length; i++ ) {
        res.push(`>seq_${i+1}`)
        res.push(String(lines[i]).trim())
      }
      formData.value.fasta = lines.join("\n")
    } else {
      formData.value.fasta = sequence.value
    }
  }
})

// used to control the input lines in sequence
const allowSequence = (value: string) => {
  // empty value then reset
  if (value === null || value === '') {
    sequence_status.value = ""
    sequence_status_message.value = 'Please enter sequences — one per line, or in FASTA format.'
    return true
  }

  // if too much lines
  let lines = value.trim().split(/\r?\n/).filter(line => line.trim() !== '');
  let status = lines.length < 20
  if (!status) {
    sequence_status.value = "error"
    sequence_status_message.value = "Only maximum 20 lines were allowed."
    return status
  }

  let input_format = "sequence"
  // check the value
  if (!value.includes(">")) {
    // normal sequences
    for (let i = 0; i < lines.length; i++) {
      if (!/^[ATCGatcg]+$/.test(String(lines[i]))) {
        sequence_status.value = "error"
        sequence_status_message.value = `try to input non ATCG characters`
        return false
      }
    }
  } else {
    input_format = "fasta"
    // fasta format
    let last_name_row = -2

    for (let i = 0; i < lines.length; i++) {
      // only check the name line, and if there is any sequence between two name line
      if (String(lines[i]).startsWith(">")) {
        if ((i - last_name_row) < 2) {
          sequence_status.value = "error"
          sequence_status_message.value = `there is no sequence between two sequence name`
          return
        }
        last_name_row = i
      } else if (!/^[ATCGatcg]+$/.test(String(lines[i]))) {
        sequence_status.value = "error"
        sequence_status_message.value = `try to input non ATCG characters`
        return false
      }
    }
  }

  sequence_status.value = status ? "success" : "error"
  sequence_status_message.value = status ? `The input ${input_format} is valid` : "Only maximum 20 lines were allowed."

  return status
}

onMounted(() => {
  axios.get(APIs.rule).then((response: AxiosResponse) => {
    let res = []
    for (let key of Object.keys(response.data)) {
      res.push(key)
    }
    pam_rule.value = res
  })

  axios.get(APIs.pam).then((response: AxiosResponse) => {
    models.value = response.data
  }).catch((error: AxiosError) => {
    showError(error)
  })

  axios.get(APIs.genome).then((response: AxiosResponse) => {
    genomes.value = response.data
  }).catch((error: AxiosError) => {
    showError(error)
  })
})

// submit parameters
const submit = () => {
  // different parameters
  let data: FormData = {
    gene: null,
    genome_range:  null,
    genome:  formData.value.genome,
    fasta: null,
    max_mismatch: formData.value.max_mismatch,
    pam: formData.value.pam,
    editing_pattern: formData.value.editing_pattern,
    off_target: off_target.value,
  }

  // set parameters for different mode
  if (activeTab.value === 'gene') {
    data.gene = formData.value.gene
  } else if (activeTab.value === 'genomic_range') {
    data.genome_range = formData.value.genome_range
  } else if (activeTab.value === 'fasta') {
    data.fasta = formData.value.fasta
  }

  if (state !== undefined) {
    axios.post(APIs.submit, data).then((response: AxiosResponse) => {
      state.task_id = response.data
    }).catch((error: AxiosError) => {
      showError(error)
    })
  }
}
</script>

<template>
  <n-form label-placement="left" >

    <n-flex justify="space-around" style="margin-right: 10px">
      <n-grid cols="5" :x-gap="12" :y-gap="8" item-responsive>

<!--    basic elements    -->
        <n-gi span="2 400:2" responsive="self">
          <n-form-item label="PAM">
            <n-grid cols="1">
              <n-gi>
                <n-select
                    v-model:value="formData.pam"
                    :options="models"
                    filterable
                    placeholder="Please select the preset PAM or input your favorite one"
                    tag clearable
                    :status="pam_input_status"
                    @create="(label: string) => {
                      label = label.toUpperCase()
                      return{label: label, value: label}
                    }"
                    @update:value="checkInputPAM"
                />
                <n-text :type="pam_input_status">
                    <span v-if="pam_input_status === 'success'">
                      valid PAM sequence
                    </span>
                    <span v-if="pam_input_status === 'warning'">
                      4 bp PAM required
                    </span>
                    <span v-else-if="pam_input_status !== 'error'">
                        Please select the preset PAM or input your favorite one
                    </span>
                    <span v-else>
                      Your customized PAM has invalid sequence
                    </span>
                </n-text>
              </n-gi>
            </n-grid>
          </n-form-item>
        </n-gi>
        <n-gi span="2 400:2" responsive="self">
          <n-form-item label="Genome">
            <n-select
                v-model:value="formData.genome"
                placeholder="Please select one of the genome"
                :options="genomes" clearable
            />
          </n-form-item>
        </n-gi>
        <n-gi span="1" responsive="self">
          <n-form-item label="Predict Off-target">
            <n-switch v-model:value="off_target" />
          </n-form-item>
        </n-gi>

        <n-gi v-if="off_target" span="2 400:2" responsive="self">
          <n-form-item label="Max mismatch (bp)" >
            <n-space vertical>
              <n-input-number
                v-model:value="formData.max_mismatch"
                placeholder="Please select one of the genome"
                min="1" max="5"
              />
              <n-text>
                Maximum mismatch allowed while predict off targets using
                <a class="n-button n-button--info-type n-button--medium-type" href="http://www.rgenome.net/cas-offinder/">
                  cas-offinder
                </a>
              </n-text>
            </n-space>
          </n-form-item>
        </n-gi>
        <n-gi v-if="off_target" span="2 400:3" responsive="self">
          <n-form-item label="Edit pattern" >
            <n-space vertical>
              <n-space>
                <n-input
                  v-model:value="formData.editing_pattern"
                  :status="editing_pattern_status"
                  maxlength="20" clearable show-count
                  placeholder="Please set the editing pattern"
                />
                <n-button
                     type="info" small quaternary
                    @click="formData.editing_pattern = 'N'.repeat(20)">
                  <template #icon>
                    <n-icon><ContentPasteSearchOutlined /></n-icon>
                  </template>
                  Autofill
                </n-button>
              </n-space>

              <n-text v-if="editing_pattern_status === 'success'" :type="editing_pattern_status">
                The editing pattern is valid
              </n-text>
              <n-text v-else-if="editing_pattern_status === 'error'" :type="editing_pattern_status">
                The input sequence contains invalid character.
              </n-text>
              <n-text v-else-if="editing_pattern_status === 'warning'" :type="editing_pattern_status">
                The editing pattern need to be exact 20 bp.
              </n-text>
              <n-text v-else :type="editing_pattern_status">
                The editing pattern used by cas-offinder, default is 20 bp N.
              </n-text>
            </n-space>
          </n-form-item>
        </n-gi>

<!--    input sequence    -->
        <n-gi span="5" responsive="self" :y-gap="8">
          <n-divider>Design sgRNA by </n-divider>
          <n-tabs type="segment" animated v-model:value="activeTab">
<!-- gene input -->
            <n-tab-pane name="gene" tab="Gene Name/ENSEMBL ID">
              <n-grid cols="9" x-gap="10">
                <n-gi span="7" offset="1">
                 <n-space vertical>
                  <n-form-item label="Gene Name/ENSEMBL ID">
                    <n-auto-complete
                        v-model:value="gene_name"
                        type="text" clearable
                        :disabled="formData.genome === null"
                        :loading="gene_input_loading"
                        :options="gene_candidate"
                        @select="chooseGene"
                        @update:value="fetchGeneInfo"
                        :placeholder="formData.genome === null ? 'please select genome first' : 'please input gene name or ensemble id'" />
                    <n-button
                        type="info" small quaternary
                        :disabled="formData.genome === null"
                        @click="gene_name = examples['gene']['label']; formData.gene = examples['gene']['value']; gene_name_status = 'success'">
                      <template #icon>
                        <n-icon><ContentPasteSearchOutlined /></n-icon>
                      </template>
                      Example
                    </n-button>
                  </n-form-item>
                  <n-blockquote align-text>Please input at least 3 characters, then choose the the gene from candidate list</n-blockquote>
                </n-space>
                </n-gi>
              </n-grid>
            </n-tab-pane>

<!-- genomic range -->
            <n-tab-pane name="genomic_range" tab="Genomic Region">
              <n-grid cols="9"  x-gap="10">
                <n-gi span="7" offset="1">
                 <n-space vertical>
                  <n-form-item label="Genomic Region">
                    <n-input
                        v-model:value="formData.genome_range"
                        type="text" clearable
                        :status="genomic_range_status"
                        :disabled="formData.genome === null"
                        placeholder="Please please input genomic region, eg: chr17:7668421-7687487"
                    />
                    <n-button
                        type="info" small quaternary
                        :disabled="formData.genome === null"
                        @click="formData.genome_range = examples['range']">
                      <template #icon>
                        <n-icon><ContentPasteSearchOutlined /></n-icon>
                      </template>
                      Example
                    </n-button>
                  </n-form-item>
                  <n-blockquote align-text>
                    <n-text v-if="genomic_range_status === 'success'" :type="genomic_range_status">
                      Genomic region is valid
                    </n-text>
                    <n-text v-else-if="genomic_range_status !== 'error'">
                      Please please input genomic region, eg: chr17:7668421-7687487
                    </n-text>
                    <n-text v-else-if="genomic_range_status === 'error'" :type="genomic_range_status">
                      Please check the input genomic region.
                    </n-text>
                  </n-blockquote>
                </n-space>
                </n-gi>
              </n-grid>
            </n-tab-pane>

<!-- sequence or fasta -->
            <n-tab-pane name="fasta" tab="Customized Fasta / sequence">
              <n-grid cols="9"  x-gap="10">
                <n-gi span="7" offset="1">
                 <n-space vertical>
                   <n-form-item>
                    <n-input
                        v-model:value="sequence" :autosize="{ minRows: 4, maxRows: 24 }"
                        type="textarea" :status="sequence_status"
                        :allow-input="allowSequence" clearable
                        :maxlength="10000" show-count
                        placeholder="Please enter sequences — one per line, or in FASTA format."
                      />

                     <n-button
                          type="info" small quaternary
                     @click="sequence = examples['fasta']; sequence_status = 'success'">
                      <template #icon>
                        <n-icon><ContentPasteSearchOutlined /></n-icon>
                      </template>
                      Example
                     </n-button>
                   </n-form-item>

                  <n-blockquote align-text>
                    <n-text :type="sequence_status">{{ sequence_status_message }}</n-text>
                  </n-blockquote>
                </n-space>
                </n-gi>
              </n-grid>
            </n-tab-pane>
          </n-tabs>

          <n-divider />
        </n-gi>

<!--    submit  -->
        <n-gi offset="2" span="1 400:1" responsive="self">
            <n-button-group>
            <n-button :disabled="!isFormValid" type="success" @click="submit">
              <template #icon>
                  <n-icon><AddTaskFilled /></n-icon>
              </template>
              Submit
            </n-button>
            <n-button type="error">
              <template #icon>
                  <n-icon><DangerousOutlined /></n-icon>
              </template>
              Reset
            </n-button>
          </n-button-group>
        </n-gi>

      </n-grid>
      <n-divider v-if="state !== undefined && state.task_id !== null">Task ID: {{state.task_id}}</n-divider>
    </n-flex>
  </n-form>
</template>

<style scoped>
a {
  --n-bezier: cubic-bezier(.4, 0, .2, 1);
  --n-bezier-ease-out: cubic-bezier(0, 0, .2, 1);
  --n-ripple-duration: .6s;
  --n-opacity-disabled: 0.5;
  --n-wave-opacity: 0.6;
  --n-font-weight: 400;
  --n-color: #0000;
  --n-color-pressed: rgba(46, 51, 56, .13);
  --n-color-focus: rgba(46, 51, 56, .09);
  --n-color-disabled: #0000;
  --n-ripple-color: #0000;
  --n-text-color: #2080f0;
  --n-text-color-hover: #2E5B88;
  --n-text-color-pressed: #2080f0;
  --n-text-color-focus: #2080f0;
  --n-text-color-disabled: #2080f0;
  --n-width: initial;
}
</style>