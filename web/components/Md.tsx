import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

export default function Md({ children }: { children: string }) {
  return (
    <div className="md">
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        components={{
          table: ({ children }) => (
            <div className="tbl"><table>{children}</table></div>
          ),
        }}
      >
        {children}
      </ReactMarkdown>
    </div>
  );
}