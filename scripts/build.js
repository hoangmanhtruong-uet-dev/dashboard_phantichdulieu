const { cpSync, existsSync, mkdirSync, readFileSync, rmSync } = require('node:fs');
const { join } = require('node:path');

const root = join(__dirname, '..');
const output = join(root, 'dist');
const assets = ['index.html', 'style.css', 'app.js', 'frontend/api-client.js', 'frontend/resource-state.js', 'frontend/resource-state.css'];
const html = readFileSync(join(root, 'index.html'), 'utf8');
for (const asset of assets) {
  if (!existsSync(join(root, asset))) throw new Error(`Missing production asset: ${asset}`);
  if (asset !== 'index.html' && !html.includes(asset)) throw new Error(`index.html does not reference ${asset}`);
}
rmSync(output, { recursive: true, force: true });
mkdirSync(join(output, 'frontend'), { recursive: true });
for (const asset of assets) cpSync(join(root, asset), join(output, asset));
console.log(`Production frontend built: ${assets.length} assets`);
