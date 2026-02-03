
export interface APIInterface {
    gene: string
    results: string
    off_target: string
    download: string
    submit: string
    status: string
    pam: string
    rule: string
    fasta: string
    genome: string
    headers: string
    upload: string
}

export interface Pagination {
    order: string
    order_by: string
    total: number
    page: number
    length: number
}

export interface FormData {
    gene: string | null
    genome_range: string | null
    genome: string | null
    fasta: string | null
    max_mismatch: 5
    pam: string | null
    editing_pattern: string | null
    model?: string | null
    chromosome?: string | null,
    start?: number | null,
    end?: number | null
    off_target: Boolean
}

export interface SelectOption {
    label: string, value: string
}

export interface JobStatus {
    id: string,
    description: string,
    parameters: FormData,
    progress: String[],
    error: String[],
    status: String
}

export interface Header {
    key: string
    title: string
    maxWidth: number |  null
    sorter: boolean
}

export interface RowData {
    id: string
    task: string
    sgrna_position: string
    before: string
    pam: string
    sgrna: string
    after: string
    target: string
    gc_content: Number
    gene_id?: string
    gene_name?: string
    range?: string
    exon_id?: string
    exon_range?: string
    name?: string
    indel_freq: number
}

export interface State {
  task_id: string | null
  status: JobStatus | null
  pagination: Pagination | null
}
