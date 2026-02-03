// src/stores/useRefreshStore.js
import type {APIInterface} from "./interfaces.ts";


export let BASE_URL = '/procas12f';  // http://localhost:8080

export let APIs: APIInterface;
APIs = {
    gene: `${BASE_URL}/api/gene`,
    results: `${BASE_URL}/api/result`,
    off_target: `${BASE_URL}/api/result/off`,
    headers: `${BASE_URL}/api/result/headers`,
    download: `${BASE_URL}/api/result/download`,
    submit: `${BASE_URL}/api/task/submit`,
    status: `${BASE_URL}/api/task/status`,
    pam: `${BASE_URL}/api/const/pam`,
    rule: `${BASE_URL}/api/const/rule`,
    fasta: `${BASE_URL}/api/const/fasta`,
    genome: `${BASE_URL}/api/const/genome`,
    upload: `${BASE_URL}/api/upload`
}


// export const useRefreshStore = defineStore('refresh', () => {
//     // 响应式状态：用于触发刷新
//     const refreshTrigger = ref(0)
//
//     const formData = ref<FormData>({
//         gene: null,
//         genome_range: null,
//         fasta: null,
//         max_mismatch: 5,
//         pam: "NTTM",
//         genome: "hg38",
//         editing_pattern: null
//     })
//
//     const pagination = ref<Pagination>({
//         order: "desc",  order_by: "indel_freq",
//         total: 10,  length: 10,  page: 1
//     })
//
//     const task_id = ref<string | null>("A3hJHJfaw69yAJhb")
//     const status = ref<JobStatus | null>(null)
//
//     return {
//         task_id,
//         refreshTrigger,
//         formData,
//         pagination,
//         status,
//     }
// })
