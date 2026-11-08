import { GuidedMode } from "./GuidedMode"

export default async function GuidaPage({
  params,
}: {
  params: Promise<{ id: string }>
}) {
  const { id } = await params
  return <GuidedMode farmacoId={id} />
}
