import { ShareCard } from "./ShareCard"

export default async function SchedaPage({
  params,
}: {
  params: Promise<{ id: string }>
}) {
  const { id } = await params
  return <ShareCard farmacoId={id} />
}
