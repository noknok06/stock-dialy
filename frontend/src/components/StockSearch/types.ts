export interface Company {
  code: string
  name: string
  industry: string
  market: string
}

export interface SearchApiResponse {
  success: boolean
  companies: Company[]
  count: number
}

export interface PriceApiResponse {
  success: boolean
  price?: number
  current_price?: number
}

export interface HiddenFieldMap {
  code?: string
  name?: string
  industry?: string
  market?: string
  price?: string
}

export interface StockSearchProps {
  apiUrl: string
  priceApiUrl: string
  inputId: string
  inputName: string
  hiddenFields: HiddenFieldMap
  placeholder?: string
  minChars?: number
}
