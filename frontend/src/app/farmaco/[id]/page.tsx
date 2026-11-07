import ClientPage from "./ClientPage"

export default async function FarmacoDetailPage({
  params,
}: {
  params: Promise<{ id: string }>
}) {
  const { id: farmacoId } = await params
  return <ClientPage farmacoId={farmacoId} />
}
