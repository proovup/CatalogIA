export default function Card({ children, className = "", onClick, hover = true, animate = true }) {
  return (
    <div
      class={`bg-white rounded-xl border border-gray-200/80 p-6 ${animate ? "animate-scale-in" : ""} ${hover ? "transition-all duration-200 hover:shadow-lg hover:shadow-gray-200/50 hover:border-gray-300/80" : ""} ${onClick ? "cursor-pointer hover:border-indigo-300 hover:shadow-indigo-100/50" : ""} ${className}`}
      onClick={onClick}
    >
      {children}
    </div>
  );
}
