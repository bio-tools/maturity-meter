// Render a radial mosaic with viz-mosaic.
// stdin: JSON {"components": [...], "options": {...}}; stdout: the SVG.
import { renderRadialMosaic } from 'viz-mosaic';

let input = '';
for await (const chunk of process.stdin) input += chunk;
const { components, options = {} } = JSON.parse(input);
process.stdout.write(renderRadialMosaic(components, options));
