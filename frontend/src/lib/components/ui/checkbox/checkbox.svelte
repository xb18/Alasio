<script lang="ts">
	import { Checkbox as CheckboxPrimitive } from "bits-ui";
	import CheckIcon from '@lucide/svelte/icons/check';
	import MinusIcon from '@lucide/svelte/icons/minus';
	import { cn, type WithoutChildrenOrChild } from "$lib/utils.js";

	let {
		ref = $bindable(null),
		checked = $bindable(false),
		indeterminate = $bindable(false),
		class: className,
		iconClass,
		iconStrokeWidth,
		...restProps
	}: WithoutChildrenOrChild<CheckboxPrimitive.RootProps> & {
		iconClass?: string;
		iconStrokeWidth?: number;
	} = $props();
</script>

<CheckboxPrimitive.Root
	bind:ref
	data-slot="checkbox"
	class={cn(
		"flex size-4 items-center justify-center rounded-[4px] border border-input shadow-xs transition-shadow group-has-disabled/field:opacity-50 focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50 aria-invalid:border-destructive aria-invalid:ring-3 aria-invalid:ring-destructive/20 aria-invalid:aria-checked:border-primary dark:bg-input/30 dark:aria-invalid:border-destructive/50 dark:aria-invalid:ring-destructive/40 data-checked:border-primary data-checked:bg-primary data-checked:text-primary-foreground dark:data-checked:bg-primary peer relative shrink-0 outline-none after:absolute after:-inset-x-3 after:-inset-y-2 disabled:cursor-not-allowed disabled:opacity-50",
		className
	)}
	bind:checked
	bind:indeterminate
	{...restProps}
>
	{#snippet children({ checked, indeterminate })}
		<div
			data-slot="checkbox-indicator"
			class="[&>svg]:size-3.5 grid place-content-center text-current transition-none"
		>
			{#if checked}
				<!-- MODIFIED: allow overriding icon attributes -->
				<CheckIcon class={cn("size-3.5", iconClass)} strokeWidth={iconStrokeWidth} />
			{:else if indeterminate}
				<MinusIcon class={cn("size-3.5", iconClass)} strokeWidth={iconStrokeWidth} />
			{:else}
				<!-- MODIFIED: Create a placeholder to keep self well aligned when parent using item-* -->
				<div class={cn("size-3.5", iconClass)}></div>
			{/if}
		</div>
	{/snippet}
</CheckboxPrimitive.Root>
