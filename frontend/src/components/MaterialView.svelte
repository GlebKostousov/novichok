<script lang="ts">
  import type { Material } from '../lib/types';
  interface Props { material: Material; collapsed?: boolean; label?: string; }
  let { material, collapsed = false, label }: Props = $props();
  const money = new Intl.NumberFormat('ru-RU', { style: 'currency', currency: 'RUB', maximumFractionDigits: 0 });
</script>

<details class="catalog" open={!collapsed}>
  <summary><span>{label ?? material.title}</span><small>Версия {material.version}</small></summary>
  <div class="catalog-body">
    {#each material.paragraphs as paragraph}<p>{paragraph}</p>{/each}
    {#if material.products.length}
      <ul class="catalog-list">
        {#each material.products as product (product.id)}
          <li>
            <div class="product-heading"><strong>{product.name}</strong><span>{money.format(product.price)}</span></div>
            <p class="product-purpose">{product.purpose}</p>
            <p class="product-features">{product.features.join(' · ')}</p>
          </li>
        {/each}
      </ul>
      <p class="catalog-note">Товары, характеристики и цены вымышлены.</p>
    {/if}
  </div>
</details>
