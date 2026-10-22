import { render, screen, waitFor } from "@testing-library/react";
import { vi } from "vitest";

import { ChatPanel } from "../components/ChatPanel";

test("chat stream scrolls to the latest incoming report", async () => {
  const { container, rerender } = render(
    <ChatPanel incomingMessage={{ id: "msg-1", content: "第一条消息" }} />
  );

  expect(await screen.findByText("第一条消息")).toBeInTheDocument();
  const stream = container.querySelector(".chat-stream") as HTMLDivElement;
  const scrollTo = vi.fn();
  Object.defineProperty(stream, "scrollHeight", { value: 720, configurable: true });
  Object.defineProperty(stream, "scrollTo", { value: scrollTo, configurable: true });

  rerender(<ChatPanel incomingMessage={{ id: "msg-2", content: "最新一条消息" }} />);
  expect(await screen.findByText("最新一条消息")).toBeInTheDocument();

  await waitFor(() => {
    expect(scrollTo).toHaveBeenLastCalledWith({ top: 720, behavior: "smooth" });
  });
});
