const BLOCK_SIZE = 7;
const BLOCK_MARGIN = 1;
const TABLE_PADDING = 0;
const COLOR_HIT = '#60a5fa';
const COLOR_MISS = '#2563eb';
const COLOR_DEFAULT = '#cbd5e1';

export interface DrawInfo {
  blocksPerRow: number;
}

export function initializeCanvas(
  canvas: HTMLCanvasElement,
  totalBlocks: number,
  canvasWidth: number
): DrawInfo {
  const ctx = canvas.getContext('2d');
  if (!ctx) throw new Error('Could not get canvas context');

  const blocksPerRow = Math.floor(
    (canvasWidth - 2 * TABLE_PADDING) / (BLOCK_SIZE + BLOCK_MARGIN)
  );

  const numRows = Math.ceil(totalBlocks / blocksPerRow);
  canvas.height = numRows * (BLOCK_SIZE + BLOCK_MARGIN) + TABLE_PADDING;

  // Draw initial grid
  ctx.clearRect(0, 0, canvas.width, canvas.height);
  ctx.fillStyle = '#f8f8f8';
  ctx.fillRect(0, 0, canvas.width, canvas.height);

  let blockX = TABLE_PADDING;
  let blockY = TABLE_PADDING;

  for (let i = 0; i < totalBlocks; i++) {
    ctx.fillStyle = COLOR_DEFAULT;
    ctx.fillRect(blockX, blockY, BLOCK_SIZE, BLOCK_SIZE);
    blockX += BLOCK_SIZE + BLOCK_MARGIN;
    if ((i + 1) % blocksPerRow === 0) {
      blockX = TABLE_PADDING;
      blockY += BLOCK_SIZE + BLOCK_MARGIN;
    }
  }

  return { blocksPerRow };
}

export function highlightBlock(
  canvas: HTMLCanvasElement,
  blockNumber: number,
  drawInfo: DrawInfo,
  hit: number
): void {
  const ctx = canvas.getContext('2d');
  if (!ctx) return;

  const { blocksPerRow } = drawInfo;
  const row = Math.floor(blockNumber / blocksPerRow);
  const col = blockNumber % blocksPerRow;

  const x = TABLE_PADDING + col * (BLOCK_SIZE + BLOCK_MARGIN);
  const y = TABLE_PADDING + row * (BLOCK_SIZE + BLOCK_MARGIN);

  // Highlight
  ctx.fillStyle = hit ? COLOR_HIT : COLOR_MISS;
  ctx.fillRect(x, y, BLOCK_SIZE, BLOCK_SIZE);
}

export function clearBlock(
  canvas: HTMLCanvasElement,
  blockNumber: number,
  drawInfo: DrawInfo
): void {
  const ctx = canvas.getContext('2d');
  if (!ctx) return;

  const { blocksPerRow } = drawInfo;
  const row = Math.floor(blockNumber / blocksPerRow);
  const col = blockNumber % blocksPerRow;

  const x = TABLE_PADDING + col * (BLOCK_SIZE + BLOCK_MARGIN);
  const y = TABLE_PADDING + row * (BLOCK_SIZE + BLOCK_MARGIN);

  // Clear highlight (reset to default color)
  ctx.fillStyle = COLOR_DEFAULT;
  ctx.fillRect(x, y, BLOCK_SIZE, BLOCK_SIZE);
}
