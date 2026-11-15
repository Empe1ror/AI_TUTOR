import ReactMarkdown from "react-markdown";
export default function Md({ children }: { children: string }) {
  return <div className="md"><ReactMarkdown>{children}</ReactMarkdown></div>;
}
