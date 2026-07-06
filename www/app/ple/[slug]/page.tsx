import { notFound } from "next/navigation";
import { PleEventDetailView } from "@/components/ple/ple-event-detail";
import { getPleBySlug } from "@/lib/wwe-ple";
import { getPleDetailBySlug } from "@/lib/wwe-ple-detail";
import { WWE_PLE_MONTHLY_ORDER } from "@/lib/wwe-ple";

type Props = { params: Promise<{ slug: string }> };

export function generateStaticParams() {
  return WWE_PLE_MONTHLY_ORDER.map((e) => ({ slug: e.slug }));
}

export default async function PleEventPage({ params }: Props) {
  const { slug } = await params;
  const ple = getPleBySlug(slug);
  const detail = getPleDetailBySlug(slug);
  if (!ple || !detail) notFound();

  return <PleEventDetailView ple={ple} detail={detail} />;
}
