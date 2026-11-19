import { notFound } from "next/navigation";
import { Terminal } from "@/components/terminal";
export function generateStaticParams() { return ["inflation", "labor", "growth", "monetary"].map(section => ({section})); }
export default async function Page({params}: {params: Promise<{section: string}>}) {
  const {section} = await params;
  if (!["inflation", "labor", "growth", "monetary"].includes(section)) notFound();
  return <Terminal section={section} />;
}
