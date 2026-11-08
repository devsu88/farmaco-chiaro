export const ICONE: Record<string, string> = {
  info: "ℹ️",
  compressa: "💊",
  divieto: "🚫",
  telefono: "📞",
  orologio: "⏰",
  doppia: "⚠️",
  allerta: "🚨",
  bicchiere: "🍷",
}

export function icona(nome: string): string {
  return ICONE[nome] ?? "•"
}
