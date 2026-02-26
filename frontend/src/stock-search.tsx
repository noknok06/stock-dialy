/**
 * Stock Search Island – entry point
 *
 * Mount by placing a container element in the Django template:
 *
 *   <div data-react="stock-search"
 *        data-api-url="/stockdiary/api/stock/search/"
 *        data-price-api-url="/stockdiary/api/stock/price/"
 *        data-input-id="stock_name_quick"
 *        data-input-name="stock_name"
 *        data-hidden-fields='{"code":"id_stock_code","price":"purchase_price_quick"}'
 *        data-placeholder="例: トヨタ自動車 または 7203">
 *   </div>
 */
import React from 'react'
import { createRoot } from 'react-dom/client'
import StockSearch from './components/StockSearch'
import type { HiddenFieldMap } from './components/StockSearch/types'

document.querySelectorAll<HTMLElement>('[data-react="stock-search"]').forEach((container) => {
  const {
    apiUrl = '/stockdiary/api/stock/search/',
    priceApiUrl = '/stockdiary/api/stock/price/',
    inputId = 'stock_name_quick',
    inputName = 'stock_name',
    hiddenFields: hiddenFieldsRaw = '{}',
    placeholder,
  } = container.dataset

  let hiddenFields: HiddenFieldMap = {}
  try {
    hiddenFields = JSON.parse(hiddenFieldsRaw)
  } catch {
    console.warn('[StockSearch] Invalid data-hidden-fields JSON', hiddenFieldsRaw)
  }

  createRoot(container).render(
    <React.StrictMode>
      <StockSearch
        apiUrl={apiUrl}
        priceApiUrl={priceApiUrl}
        inputId={inputId}
        inputName={inputName}
        hiddenFields={hiddenFields}
        placeholder={placeholder}
      />
    </React.StrictMode>,
  )
})
