// Lista curata dei farmaci più comuni mostrata in home.
// Gli id sono quelli del dataset AIFA (formato "NNNNNN_NN").

export interface FarmacoComune {
  id: string
  nome: string
}

export const FARMACI_COMUNI: FarmacoComune[] = [
  { id: "012745_01", nome: "Tachipirina" },
  { id: "025669_01", nome: "Moment" },
  { id: "034248_04", nome: "Gaviscon Advance" },
  { id: "004763_01", nome: "Aspirina" },
  { id: "034764_02", nome: "Subitene" },
]

// Numero di farmaci unici nel catalogo (drug_id distinti in
// backend/data/rag/sections.jsonl alla build 2026-11-14). Si aggiorna
// manualmente insieme ai dati del catalogo.
export const TOTALE_FARMACI = 454
