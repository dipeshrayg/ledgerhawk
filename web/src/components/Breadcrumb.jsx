import { Link } from "react-router-dom";

export function Breadcrumb({ trail }) {
  return (
    <nav aria-label="Breadcrumb" className="mb-3 flex items-center gap-1.5 text-sm text-neutral-500 dark:text-neutral-400">
      {trail.map((item, i) => (
        <span key={i} className="flex items-center gap-1.5">
          {i > 0 && <span aria-hidden="true">/</span>}
          {item.to ? (
            <Link to={item.to} className="hover:text-neutral-900 hover:underline dark:hover:text-neutral-100">
              {item.label}
            </Link>
          ) : (
            <span aria-current="page" className="text-neutral-900 dark:text-neutral-100">
              {item.label}
            </span>
          )}
        </span>
      ))}
    </nav>
  );
}
