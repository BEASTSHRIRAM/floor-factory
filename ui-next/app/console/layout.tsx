import ConsoleShell from "../../components/ConsoleShell";
import "./ao.css";

/* Every /console route shares the console shell (sidebar + session
 * guard). The board page keeps its own ao.css import as well; the
 * duplicate import of the same file is deduplicated by the bundler. */
export default function ConsoleLayout({ children }: { children: React.ReactNode }) {
  return <ConsoleShell>{children}</ConsoleShell>;
}
