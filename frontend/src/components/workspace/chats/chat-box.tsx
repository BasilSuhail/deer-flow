const ChatBox: React.FC<{ children: React.ReactNode; threadId: string }> = ({
  children,
}) => {
  return (
    <div className="relative size-full">
      {children}
    </div>
  );
};

export { ChatBox };
