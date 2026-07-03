"use client";

import { Source } from "@/lib/api";
import { getSourceFallbackLetter, getSourceImageUrl } from "@/lib/source-image";
import {
  Avatar,
  AvatarFallback,
  AvatarGroup,
  AvatarGroupCount,
  AvatarImage,
} from "@/components/ui/avatar";
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip";

function SourceAvatar({ source }: { source: Source }) {
  const imageUrl = getSourceImageUrl(source.url);
  const fallback = getSourceFallbackLetter(source);
  const tooltip = source.title ? `${source.title}\n${source.url}` : source.url;

  return (
    <Tooltip>
      <TooltipTrigger
        render={
          <a
            href={source.url}
            target="_blank"
            rel="noopener noreferrer"
            aria-label={source.title || source.url}
            className="rounded-full outline-none ring-offset-background transition-transform hover:z-10 hover:scale-110 focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
            onClick={(event) => event.stopPropagation()}
          />
        }
      >
        <Avatar size="xs" className="border-2 border-background">
          {imageUrl && (
            <AvatarImage src={imageUrl} alt={source.title || source.url} />
          )}
          <AvatarFallback>{fallback}</AvatarFallback>
        </Avatar>
      </TooltipTrigger>
      <TooltipContent side="top" className="max-w-sm whitespace-pre-wrap break-all">
        {tooltip}
      </TooltipContent>
    </Tooltip>
  );
}

export function SourceAvatarGroup({
  sources,
  maxVisible = 4,
}: {
  sources: Source[];
  maxVisible?: number;
}) {
  if (sources.length === 0) return null;

  const visible = sources.slice(0, maxVisible);
  const hiddenCount = sources.length - visible.length;

  return (
    <AvatarGroup className="-space-x-1.5 *:data-[slot=avatar]:ring-2 *:data-[slot=avatar]:ring-background *:data-[slot=avatar-group-count]:border-2 *:data-[slot=avatar-group-count]:border-background *:data-[slot=avatar-group-count]:ring-2 *:data-[slot=avatar-group-count]:ring-background">
      {visible.map((source) => (
        <SourceAvatar key={source.id} source={source} />
      ))}
      {hiddenCount > 0 && (
        <Tooltip>
          <TooltipTrigger render={<span className="cursor-default" />}>
            <AvatarGroupCount className="border-2 border-background">
              +{hiddenCount}
            </AvatarGroupCount>
          </TooltipTrigger>
          <TooltipContent side="top" className="max-w-sm space-y-1">
            {sources.slice(maxVisible).map((source) => (
              <a
                key={source.id}
                href={source.url}
                target="_blank"
                rel="noopener noreferrer"
                className="block truncate hover:underline"
                onClick={(event) => event.stopPropagation()}
              >
                {source.title || source.url}
              </a>
            ))}
          </TooltipContent>
        </Tooltip>
      )}
    </AvatarGroup>
  );
}
