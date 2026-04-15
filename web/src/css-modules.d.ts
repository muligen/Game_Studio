declare module '*.css' {
  const content: { [className: string]: string }
  export default content
}

declare module '*.css' {
  const css: string
  export default css
}
