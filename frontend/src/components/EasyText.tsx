"use client"

interface EasyTextProps {
  unaFrase: string | null
  versioneFacile: string[] | null
  glossario: { termine: string; spiegazione: string }[] | null
  domandeFarmacista: string[] | null
}

export function EasyText({ unaFrase, versioneFacile, glossario, domandeFarmacista }: EasyTextProps) {
  const haVersione = !!versioneFacile && versioneFacile.length > 0

  if (!haVersione) {
    return (
      <div className="bg-white border border-green-200 rounded-lg p-4 max-h-[60vh] overflow-y-auto">
        <div className="flex items-center gap-2 mb-2">
          <span className="w-2 h-2 rounded-full bg-green-500"></span>
          <span className="text-xs font-medium text-green-700 uppercase tracking-wider">Versione facile da leggere</span>
        </div>
        <div className="p-3 bg-amber-50 rounded border border-amber-100">
          <p className="text-sm text-amber-800">
            La versione semplificata non è disponibile al momento (servizio AI non configurato). Puoi comunque leggere il foglio illustrativo originale a sinistra.
          </p>
        </div>
      </div>
    )
  }

  return (
    <div className="bg-white border border-green-200 rounded-lg p-4 max-h-[60vh] overflow-y-auto">
      <div className="mb-4 flex items-center gap-2">
        <span className="w-2 h-2 rounded-full bg-green-500"></span>
        <span className="text-xs font-medium text-green-700 uppercase tracking-wider">Versione facile da leggere</span>
      </div>

      {/* Una frase */}
      <div className="mb-4 p-3 bg-blue-50 rounded border border-blue-100">
        <p className="text-sm font-semibold text-blue-900">{unaFrase}</p>
      </div>

      {/* Versione facile */}
      <div className="mb-4">
        <p className="text-xs font-medium text-gray-600 uppercase tracking-wider mb-2">Cosa devi sapere</p>
        <ul className="space-y-2 text-sm text-gray-800 leading-relaxed">
          {versioneFacile.map((frase, i) => (
            <li key={i} className="flex gap-2">
              <span className="text-green-600">✓</span>
              <span>{frase}</span>
            </li>
          ))}
        </ul>
      </div>

      {/* Glossario */}
      {glossario && glossario.length > 0 && (
        <div className="mb-4">
          <p className="text-xs font-medium text-gray-600 uppercase tracking-wider mb-2">Parole difficili</p>
          <dl className="space-y-1 text-sm">
            {glossario.map((g, i) => (
              <div key={i} className="flex justify-between border-b border-gray-100 pb-1 last:border-0">
                <dt className="text-gray-700 font-medium">{g.termine}</dt>
                <dd className="text-gray-600">{g.spiegazione}</dd>
              </div>
            ))}
          </dl>
        </div>
      )}

      {/* Domande al farmacista */}
      <div className="pt-4 border-t border-gray-100">
        <p className="text-xs font-medium text-gray-600 uppercase tracking-wider mb-2">Domande da fare al farmacista</p>
        <ul className="space-y-1 text-sm text-gray-800">
          {(domandeFarmacista || []).map((d, i) => (
            <li key={i} className="flex items-start gap-2">
              <span className="text-gray-400 mt-0.5">•</span>
              <span>{d}</span>
            </li>
          ))}
        </ul>
      </div>
    </div>
  )
}
