import baseConfig from './playwright.config'

export default {
  ...baseConfig,
  use: {
    ...baseConfig.use,
    screenshot: 'on',
    video: 'on',
    trace: 'on',
  },
}
